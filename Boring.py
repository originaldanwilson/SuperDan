#from mj import jiggle_mouse
import time
import pyautogui
import random

def alt_tab():
    tabCount = random.randint(1, 5)
    pyautogui.keyDown('alt')
    time.sleep(tabCount)
    for i in range(tabCount):
        pyautogui.keyDown('tab')
        time.sleep(1)
    pyautogui.keyUp('alt')

def sleep_loop():
    while True:
        alt_tab()
        x = random.randint(1, 60)
        print(f"resting for {x} seconds ..")
        time.sleep(x)

def main():
    sleep_loop()
    #while True:
    #    #jiggle_mouse(interval=30)
    #    alt_tab()
    #    time.sleep(30)

if __name__ == "__main__":
    main()
