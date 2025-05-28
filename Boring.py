import time
from mj import jiggle_mouse
from pywinauto import Desktop

def get_window_list():
    windows = []
    for w in Desktop(backend="uia").windows():
        try:
            if w.is_visible() and w.window_text().strip():
                windows.append(w)
        except Exception:
            continue
    return windows

def main():
    windows = get_window_list()
    index = 0

    while windows:
        try:
            jiggle_mouse(interval=30)
            win = windows[index % len(windows)]
            print(f"Switching to: {win.window_text()}")
            win.set_focus()
        except Exception as e:
            print(f"Error focusing window: {e}")
        index += 1
        time.sleep(30)

if __name__ == "__main__":
    main()
