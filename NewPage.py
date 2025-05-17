import webbrowser
import time

url = "https://your-confluence-page-url.com"

def open_every_15_minutes():
    print("Starting browser automation...")
    try:
        while True:
            webbrowser.open_new_tab(url)
            print(f"Opened {url}")
            time.sleep(900)  # 15 minutes = 900 seconds
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    open_every_15_minutes()
