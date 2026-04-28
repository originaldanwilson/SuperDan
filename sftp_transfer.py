#!/usr/bin/env python3
"""
sftp_transfer.py
================
Authored for: Super Dan
Maintainer:   Super Dan <originalDanWilson on GitHub>

SFTP client with:
  - Live progress (bytes, bits, percent, rate, ETA) via Rich
  - Resume-on-failure for uploads and downloads
  - Host key verification via ~/.ssh/known_hosts (reject unknown by default)
  - Cisco NX-OS friendly mode (legacy algorithms, keepalives, no pipelining/
    compression, conservative chunk size, bootflash:/ path translation)
  - Friendly error handling for connection, auth, and transfer failures

Usage:
  python sftp_transfer.py --host SW1 --user admin --nxos put image.bin bootflash:image.bin
  python sftp_transfer.py --host SW1 --user admin --nxos get bootflash:log.txt .\\log.txt
"""
from __future__ import annotations

import argparse
import errno
import getpass
import os
import socket
import sys
from pathlib import Path

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    NoValidConnectionsError,
    SSHException,
)
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    ProgressColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.text import Text

console = Console()

# Exit codes
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONNECT = 10
EXIT_AUTH = 11
EXIT_HOSTKEY = 12
EXIT_SSH = 13
EXIT_TRANSFER = 20
EXIT_LOCAL_IO = 21
EXIT_INTERRUPTED = 130


# ---------- formatting helpers ----------------------------------------------

def fmt_bits(bits: float) -> str:
    for unit in ("bit", "Kibit", "Mibit", "Gibit", "Tibit"):
        if bits < 1024.0:
            return f"{bits:,.2f} {unit}"
        bits /= 1024.0
    return f"{bits:,.2f} Pibit"


class BitsTransferredColumn(ProgressColumn):
    """Total bits transferred (e.g. '1.23 Gibit')."""
    def render(self, task) -> Text:
        return Text(fmt_bits((task.completed or 0) * 8), style="cyan")


class BitRateColumn(ProgressColumn):
    """Current rate in bits/sec (e.g. '78.40 Mibit/s')."""
    def render(self, task) -> Text:
        speed = task.speed  # bytes/sec
        if speed is None:
            return Text("-- bit/s", style="yellow")
        return Text(f"{fmt_bits(speed * 8)}/s", style="yellow")


def normalize_remote_path(path: str) -> str:
    """Translate Cisco-style paths like 'bootflash:foo' -> '/bootflash/foo'."""
    if ":" in path and not path.startswith("/"):
        fs, _, rest = path.partition(":")
        return f"/{fs}/{rest.lstrip('/')}"
    return path


# ---------- connection ------------------------------------------------------

def make_client(args) -> paramiko.SSHClient:
    client = paramiko.SSHClient()

    # Host-key verification using user's and system known_hosts files.
    client.load_system_host_keys()
    user_known = Path.home() / ".ssh" / "known_hosts"
    if user_known.exists():
        try:
            client.load_host_keys(str(user_known))
        except IOError as exc:
            console.print(f"[yellow]Warning: could not load {user_known}: {exc}[/]")

    if args.insecure:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    connect_kwargs = dict(
        hostname=args.host,
        port=args.port,
        username=args.user,
        timeout=args.timeout,
        allow_agent=True,
        look_for_keys=True,
    )
    if args.password:
        connect_kwargs["password"] = args.password
    if args.key:
        connect_kwargs["key_filename"] = args.key

    if args.nxos:
        # Older NX-OS images don't speak rsa-sha2-*; force ssh-rsa (SHA-1).
        connect_kwargs["disabled_algorithms"] = {
            "pubkeys": ["rsa-sha2-256", "rsa-sha2-512"],
        }
        connect_kwargs["banner_timeout"] = max(args.timeout, 30)
        connect_kwargs["auth_timeout"] = max(args.timeout, 30)

    client.connect(**connect_kwargs)

    transport = client.get_transport()
    if transport is not None:
        # Keep the SSH session alive across slow flash writes on NX-OS.
        transport.set_keepalive(15 if args.nxos else 30)
        if args.nxos:
            transport.use_compression(False)

    return client


# ---------- transfer core ---------------------------------------------------

CHUNK_DEFAULT = 32768
CHUNK_NXOS = 8192


def _progress_columns():
    return (
        TextColumn("[bold blue]{task.fields[label]}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TextColumn("•"),
        DownloadColumn(),
        TextColumn("•"),
        BitsTransferredColumn(),
        TextColumn("•"),
        TransferSpeedColumn(),
        TextColumn("•"),
        BitRateColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("/"),
        TimeRemainingColumn(),
    )


def stream_with_progress(src_read, dst_write, *, total, start_at, label, chunk_size):
    with Progress(*_progress_columns(), console=console, transient=False) as progress:
        task = progress.add_task("t", total=total, completed=start_at, label=label)
        while True:
            data = src_read(chunk_size)
            if not data:
                break
            dst_write(data)
            progress.update(task, advance=len(data))


def do_put(sftp, local, remote, *, resume, nxos):
    if not os.path.isfile(local):
        raise FileNotFoundError(errno.ENOENT, "Local file not found", local)

    remote = normalize_remote_path(remote)
    local_size = os.path.getsize(local)

    start_at = 0
    if resume:
        try:
            start_at = sftp.stat(remote).st_size or 0
        except IOError:
            start_at = 0
        if start_at > local_size:
            console.print(
                f"[yellow]Remote ({start_at}B) > local ({local_size}B); restarting at 0.[/]"
            )
            start_at = 0
        elif start_at == local_size:
            console.print(
                f"[green]Already complete on remote ({local_size}B); nothing to do.[/]"
            )
            return

    chunk = CHUNK_NXOS if nxos else CHUNK_DEFAULT
    mode = "ab" if start_at > 0 else "wb"

    with open(local, "rb") as fl:
        fl.seek(start_at)
        with sftp.file(remote, mode) as fr:
            try:
                fr.set_pipelined(not nxos)
            except Exception:
                pass
            stream_with_progress(
                src_read=fl.read,
                dst_write=fr.write,
                total=local_size,
                start_at=start_at,
                label=f"PUT  {Path(local).name}",
                chunk_size=chunk,
            )

    if not nxos:
        # NX-OS frequently returns stale stat right after a write; skip there.
        remote_size = sftp.stat(remote).st_size
        if remote_size != local_size:
            raise IOError(
                f"size mismatch after upload: remote={remote_size} local={local_size}"
            )


def do_get(sftp, remote, local, *, resume, nxos):
    remote = normalize_remote_path(remote)
    try:
        remote_size = sftp.stat(remote).st_size or 0
    except FileNotFoundError:
        raise
    except IOError as exc:
        # Wrap the opaque paramiko IOError into something more useful.
        raise IOError(f"could not stat {remote}: {exc}") from exc

    start_at = 0
    if resume and os.path.exists(local):
        start_at = os.path.getsize(local)
        if start_at > remote_size:
            console.print(
                f"[yellow]Local ({start_at}B) > remote ({remote_size}B); restarting at 0.[/]"
            )
            start_at = 0
            os.remove(local)
        elif start_at == remote_size:
            console.print(
                f"[green]Already complete locally ({remote_size}B); nothing to do.[/]"
            )
            return

    chunk = CHUNK_NXOS if nxos else CHUNK_DEFAULT
    mode = "ab" if start_at > 0 else "wb"

    with sftp.file(remote, "rb") as fr:
        try:
            fr.set_pipelined(not nxos)
        except Exception:
            pass
        fr.seek(start_at)
        with open(local, mode) as fl:
            stream_with_progress(
                src_read=fr.read,
                dst_write=fl.write,
                total=remote_size,
                start_at=start_at,
                label=f"GET  {Path(remote).name}",
                chunk_size=chunk,
            )

    final = os.path.getsize(local)
    if final != remote_size:
        raise IOError(
            f"size mismatch after download: local={final} remote={remote_size}"
        )


# ---------- CLI -------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SFTP transfer with resume, host-key verification, and live progress."
    )
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=22)
    p.add_argument(
        "--user",
        default=os.environ.get("USER") or os.environ.get("USERNAME") or "admin",
    )
    p.add_argument("--password", default=os.environ.get("SFTP_PASS"))
    p.add_argument("--key", help="Path to private key file.")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument(
        "--insecure",
        action="store_true",
        help="Auto-add unknown host keys to known_hosts (TOFU).",
    )
    p.add_argument(
        "--nxos",
        action="store_true",
        help="Cisco NX-OS-friendly mode.",
    )
    p.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Disable resume; always start from byte 0.",
    )
    p.set_defaults(resume=True)

    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("put"); sp.add_argument("local"); sp.add_argument("remote")
    sg = sub.add_parser("get"); sg.add_argument("remote"); sg.add_argument("local")

    args = p.parse_args()
    if not args.password and not args.key and sys.stdin.isatty():
        args.password = getpass.getpass(f"Password for {args.user}@{args.host}: ") or None
    return args


# ---------- error handling --------------------------------------------------

def _connect(args) -> paramiko.SSHClient:
    """Connect with friendly error mapping."""
    try:
        return make_client(args)
    except BadHostKeyException as exc:
        console.print(
            f"[bold red]Host key mismatch for {args.host}![/] "
            f"Server presented {exc.key.get_name()} fingerprint "
            f"{exc.key.get_fingerprint().hex()}; "
            f"expected {exc.expected_key.get_name()} "
            f"{exc.expected_key.get_fingerprint().hex()}.\n"
            "Refusing to connect. If this change is legitimate, remove the old "
            "entry from ~/.ssh/known_hosts and retry."
        )
        sys.exit(EXIT_HOSTKEY)
    except SSHException as exc:
        msg = str(exc)
        if "not found in known_hosts" in msg.lower():
            console.print(
                f"[bold red]Unknown host:[/] {args.host} is not in known_hosts.\n"
                "Re-run with [cyan]--insecure[/] to trust on first use, or add "
                "the key manually with [cyan]ssh-keyscan[/]."
            )
            sys.exit(EXIT_HOSTKEY)
        console.print(f"[bold red]SSH error:[/] {msg}")
        sys.exit(EXIT_SSH)
    except AuthenticationException:
        console.print(
            f"[bold red]Authentication failed[/] for {args.user}@{args.host}. "
            "Check the username, password, or private key."
        )
        sys.exit(EXIT_AUTH)
    except NoValidConnectionsError as exc:
        console.print(
            f"[bold red]Could not connect[/] to {args.host}:{args.port} "
            f"({exc.errors and list(exc.errors.values())[0]})."
        )
        sys.exit(EXIT_CONNECT)
    except socket.gaierror as exc:
        console.print(f"[bold red]DNS resolution failed[/] for {args.host}: {exc}")
        sys.exit(EXIT_CONNECT)
    except socket.timeout:
        console.print(
            f"[bold red]Connection to {args.host}:{args.port} timed out "
            f"after {args.timeout:.0f}s.[/]"
        )
        sys.exit(EXIT_CONNECT)
    except OSError as exc:
        # Generic socket-level failure (refused, unreachable, etc.)
        console.print(
            f"[bold red]Network error[/] connecting to {args.host}:{args.port}: {exc}"
        )
        sys.exit(EXIT_CONNECT)


def main() -> int:
    args = parse_args()

    client = _connect(args)
    try:
        try:
            sftp = client.open_sftp()
        except SSHException as exc:
            console.print(f"[bold red]Failed to open SFTP channel:[/] {exc}")
            return EXIT_SSH

        try:
            if args.cmd == "put":
                do_put(sftp, args.local, args.remote, resume=args.resume, nxos=args.nxos)
            else:
                do_get(sftp, args.remote, args.local, resume=args.resume, nxos=args.nxos)
        except FileNotFoundError as exc:
            console.print(f"[bold red]File not found:[/] {exc}")
            return EXIT_LOCAL_IO
        except PermissionError as exc:
            console.print(f"[bold red]Permission denied:[/] {exc}")
            return EXIT_LOCAL_IO
        except IOError as exc:
            console.print(f"[bold red]Transfer failed:[/] {exc}")
            console.print(
                "[yellow]Re-run the same command to resume from where it stopped.[/]"
            )
            return EXIT_TRANSFER
        except SSHException as exc:
            console.print(f"[bold red]SSH error during transfer:[/] {exc}")
            return EXIT_SSH
        finally:
            try:
                sftp.close()
            except Exception:
                pass
    finally:
        try:
            client.close()
        except Exception:
            pass

    console.print("[bold green]Done.[/]")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Interrupted by user. Partial transfer preserved; "
            "rerun the same command to resume.[/]"
        )
        sys.exit(EXIT_INTERRUPTED)
