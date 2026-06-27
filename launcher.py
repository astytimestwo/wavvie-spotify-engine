import socket
import threading
import time
import webbrowser
import os

import api
import uvicorn


HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"


def should_open_browser():
    return os.getenv("WAVEFEED_NO_BROWSER") != "1"


def wait_for_server(timeout_seconds=20):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def open_when_ready():
    if wait_for_server():
        webbrowser.open(URL)


def main():
    if should_open_browser():
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(api.app, host=HOST, port=PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()
