import argparse
import datetime
import random
import time

import pyautogui


def alt_tab():
    tab_count = random.randint(1, 5)
    pyautogui.keyDown('alt')
    time.sleep(tab_count)
    for _ in range(tab_count):
        pyautogui.keyDown('tab')
        time.sleep(1)
    pyautogui.keyUp('alt')


def sleep_loop(stop_at=None):
    """
    Run alt-tab loop until Ctrl-C or, if stop_at is given,
    until that datetime is reached.
    """
    if stop_at:
        print(f"Running until {stop_at.strftime('%H:%M')}  (Ctrl-C to stop early)")
    else:
        print("Running until Ctrl-C")

    try:
        while True:
            if stop_at and datetime.datetime.now() >= stop_at:
                print(f"\nReached stop time {stop_at.strftime('%H:%M')} — mission completed.")
                break
            alt_tab()
            rest = random.randint(1, 60)
            now  = datetime.datetime.now().strftime('%H:%M:%S')
            if stop_at:
                remaining = int((stop_at - datetime.datetime.now()).total_seconds() / 60)
                print(f"[{now}] resting {rest}s  ({remaining} min remaining)")
            else:
                print(f"[{now}] resting {rest}s")
            time.sleep(rest)
    except KeyboardInterrupt:
        print("\nMission completed.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Keeps your session alive by alt-tabbing periodically.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python Boring.py                 # run until Ctrl-C
  python Boring.py --until 17:30   # run until 5:30 PM today
  python Boring.py --for 60        # run for 60 minutes"""
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--until',
        metavar='HH:MM',
        help='stop at this time today (24-hour format, e.g. 17:30)'
    )
    group.add_argument(
        '--for',
        dest='minutes',
        metavar='MINUTES',
        type=int,
        help='stop after this many minutes'
    )

    return parser.parse_args()


def main():
    args = parse_args()
    stop_at = None

    if args.until:
        try:
            t = datetime.datetime.strptime(args.until, '%H:%M').time()
            stop_at = datetime.datetime.combine(datetime.date.today(), t)
            if stop_at <= datetime.datetime.now():
                print(f"Error: {args.until} is already in the past.")
                raise SystemExit(1)
        except ValueError:
            print(f"Error: '{args.until}' is not a valid time — use HH:MM (e.g. 17:30)")
            raise SystemExit(1)

    elif args.minutes:
        if args.minutes <= 0:
            print("Error: --for requires a positive number of minutes.")
            raise SystemExit(1)
        stop_at = datetime.datetime.now() + datetime.timedelta(minutes=args.minutes)
        print(f"Will stop at {stop_at.strftime('%H:%M')} ({args.minutes} min from now)")

    sleep_loop(stop_at)


if __name__ == "__main__":
    main()
