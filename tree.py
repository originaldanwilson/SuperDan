#!/usr/bin/env python3
"""
A Python implementation of the Unix 'tree' command.
Displays directory structure in a tree-like format.
"""

import os
import sys
from pathlib import Path


def tree(
    directory=".",
    prefix="",
    is_last=True,
    max_depth=None,
    current_depth=0,
    show_hidden=False,
    ignore_dirs=None,
):
    """
    Recursively print directory tree structure.
    
    Args:
        directory: Starting directory path
        prefix: Current line prefix for tree formatting
        is_last: Whether this is the last item in parent directory
        max_depth: Maximum recursion depth (None for unlimited)
        current_depth: Current recursion depth
        show_hidden: Whether to show hidden files/directories
        ignore_dirs: Set of directory names to ignore
    """
    if ignore_dirs is None:
        ignore_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules"}

    # Check depth limit
    if max_depth is not None and current_depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        return

    # Filter hidden files if needed
    if not show_hidden:
        entries = [e for e in entries if not e.startswith(".")]

    # Filter ignored directories
    entries = [e for e in entries if e not in ignore_dirs or os.path.isfile(os.path.join(directory, e))]

    # Separate directories and files
    dirs = []
    files = []
    for entry in entries:
        path = os.path.join(directory, entry)
        if os.path.isdir(path):
            dirs.append(entry)
        else:
            files.append(entry)

    # Combine: directories first, then files
    items = dirs + files

    for i, item in enumerate(items):
        path = os.path.join(directory, item)
        is_last_item = i == len(items) - 1

        # Determine the connector characters
        connector = "└── " if is_last_item else "├── "
        extension = "    " if is_last_item else "│   "

        # Print current item
        print(f"{prefix}{connector}{item}")

        # Recurse into directories
        if os.path.isdir(path):
            new_prefix = prefix + extension
            tree(
                path,
                new_prefix,
                is_last_item,
                max_depth,
                current_depth + 1,
                show_hidden,
                ignore_dirs,
            )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Display directory tree structure (Python implementation of tree command)"
    )
    parser.add_argument(
        "directory", nargs="?", default=".", help="Starting directory (default: current directory)"
    )
    parser.add_argument(
        "-L", "--max-depth", type=int, help="Limit recursion depth"
    )
    parser.add_argument(
        "-a", "--all", action="store_true", help="Show hidden files"
    )
    parser.add_argument(
        "-I", "--ignore", help="Comma-separated list of directories to ignore"
    )

    args = parser.parse_args()

    # Parse ignore list
    ignore_dirs = None
    if args.ignore:
        ignore_dirs = set(args.ignore.split(","))

    # Print root directory
    print(args.directory)

    # Generate tree
    tree(
        args.directory,
        max_depth=args.max_depth,
        show_hidden=args.all,
        ignore_dirs=ignore_dirs,
    )


if __name__ == "__main__":
    main()
