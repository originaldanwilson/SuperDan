import pyautogui
import time

def jiggle_mouse(interval=60):
    print("Mouse jiggler started. Move the mouse manually to stop.")
    try:
        while True:
            pyautogui.moveRel(1, 0, duration=0.1)
            pyautogui.moveRel(-1, 0, duration=0.1)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Mouse jiggler stopped.")

if __name__ == "__main__":
    jiggle_mouse(interval=60)  # Jiggle every 60 seconds
