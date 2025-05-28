import time
from mj import jiggle_mouse
from pywinauto import Desktop

def get_windows():
    return [w for w in Desktop(backend="win32").windows()
            if w.is_visible() and w.window_text().strip()]

def main():
    windows = get_windows()
    index = 0

    while windows:
        jiggle_mouse(interval=30)
        try:
            win = windows[index % len(windows)]
            print(f"Switching to: {win.window_text()}")
            win.set_focus()
        except Exception as e:
            print(f"Could not focus window: {e}")
        index += 1
        time.sleep(30)

if __name__ == "__main__":
    main()
