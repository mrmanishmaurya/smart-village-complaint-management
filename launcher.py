import os
import sys
import socket
import time
import threading
import urllib.request
import webbrowser
import logging

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

CENTRAL_BACKEND_URL = os.environ.get("CENTRAL_BACKEND_URL", "https://smart-village-complaint-management.onrender.com/smartvillage")
USE_LOCAL_BACKEND = os.environ.get("USE_LOCAL_BACKEND", "false").lower() in ("true", "1")

# Single-instance lock port to avoid multiple server instances
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
    return start_port

def start_local_flask(host, port):
    from app import app
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

def main():
    target_url = CENTRAL_BACKEND_URL

    if not check_single_instance():
        print("Smart Village Management client is already running.")
        webbrowser.open(target_url)
        sys.exit(0)

    if USE_LOCAL_BACKEND:
        print("[CLIENT LAUNCHER] Starting local development backend on 0.0.0.0:5000...")
        port = 5000
        host = "0.0.0.0"
        server_thread = threading.Thread(target=start_local_flask, args=(host, port), daemon=True)
        server_thread.start()
        target_url = "http://127.0.0.1:5000/smartvillage"
    else:
        print(f"[CLIENT LAUNCHER] Connecting to Central Online Backend: {target_url}")

    if HAS_WEBVIEW:
        print(f"Opening Smart Village Desktop App at {target_url}...")
        webview.create_window(
            title="Smart Village Complaint Management System",
            url=target_url,
            width=1280,
            height=800,
            min_size=(1024, 600),
            resizable=True
        )
        webview.start()
    else:
        print(f"Opening Smart Village Management interface at {target_url}...")
        webbrowser.open(target_url)

    if _lock_socket:
        try:
            _lock_socket.close()
        except Exception:
            pass
    sys.exit(0)

if __name__ == "__main__":
    main()

