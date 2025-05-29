from mj import jiggle_mouse
import time

def alt_tab():
    pyautogui.keyDown('alt')
    time.sleep(0.3)
    pyautogui.press('tab')
    time.sleep(0.5)
    pyautogui.keyUp('alt')
    time.sleep(1)

def main():
    while True:
        jiggle_mouse(interval=30)
        alt_tab()
        time.sleep(30)

if __name__ == "__main__":
    main()
