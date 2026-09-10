import sys
import os
import socket
import time
import threading
import urllib.request
import logging

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

import webbrowser
from app import get_resource_path

CENTRAL_BACKEND_URL = os.environ.get("CENTRAL_BACKEND_URL", "https://smart-village-complaint-management.onrender.com/smartvillage")
USE_LOCAL_BACKEND = os.environ.get("USE_LOCAL_BACKEND", "false").lower() in ("true", "1")

# Single instance lock mechanism
LOCK_PORT = 49152
_lock_socket = None

def check_single_instance():
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', LOCK_PORT))
        _lock_socket.listen(1)
        return True
    except OSError:
        return False

def find_free_port(start_port=5000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return 5000

def start_local_flask(host, port):
    from app import app
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

def main():
    if not check_single_instance():
        print("Smart Village Complaint Management System is already running.")
        sys.exit(0)

    target_url = CENTRAL_BACKEND_URL

    if USE_LOCAL_BACKEND:
        print("[CLIENT MODE] Starting local development server on 0.0.0.0:5000...")
        port = 5000
        host = "0.0.0.0"
        server_thread = threading.Thread(target=start_local_flask, args=(host, port), daemon=True)
        server_thread.start()
        target_url = "http://127.0.0.1:5000/smartvillage"
    else:
        print(f"[CLIENT MODE] Connecting directly to Central Online Backend: {target_url}")

    icon_path = get_resource_path("smart_village.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    if HAS_WEBVIEW:
        print("Launching native desktop window...")
        webview.create_window(
            title="Smart Village Complaint Management System",
            url=target_url,
            width=1280,
            height=800,
            min_size=(1024, 600),
            resizable=True
        )
        webview.start(icon=icon_path if icon_path and os.path.exists(icon_path) else None)
    else:
        print(f"Opening browser client window at {target_url}...")
        webbrowser.open(target_url)

    if _lock_socket:
        try:
            _lock_socket.close()
        except Exception:
            pass
    sys.exit(0)

if __name__ == "__main__":
    main()
