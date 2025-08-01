import sys
import threading
import time

class Spinner:
    def __init__(self, message="Working...", delay=0.1):
        self.message = message
        self.delay = delay
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin)
        self._is_running = False

    def _spin(self):
        spinner_cycle = "|/-\\"
        i = 0
        while not self._stop_event.is_set():
            sys.stdout.write(f"\r{self.message} {spinner_cycle[i % len(spinner_cycle)]}")
            sys.stdout.flush()
            time.sleep(self.delay)
            i += 1
        sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")  # Clear line

    def start(self):
        if not self._is_running:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._spin)
            self._thread.start()
            self._is_running = True

    def stop(self):
        if self._is_running:
            self._stop_event.set()
            self._thread.join()
            self._is_running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
