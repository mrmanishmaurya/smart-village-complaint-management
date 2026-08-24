import sys
import os
import socket
import time
import threading
import urllib.request
import logging
import webview
from app import app, get_resource_path

# Suppress verbose Flask / Werkzeug logs for clean desktop experience
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
cli = sys.modules.get('flask.cli')
if cli:
    cli.show_server_banner = lambda *x: None

def find_free_port(start_port=5000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return 5000

def start_flask(host, port):
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

def wait_for_server(url, timeout=15):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False

def main():
    port = find_free_port(5000)
    host = "127.0.0.1"

    server_thread = threading.Thread(target=start_flask, args=(host, port), daemon=True)
    server_thread.start()

    target_url = f"http://{host}:{port}/smartvillage"

    # Wait for Flask backend readiness
    wait_for_server(target_url)

    icon_path = get_resource_path("smart_village.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    # Launch Native PyWebView Desktop Window
    webview.create_window(
        title="Smart Village Complaint Management System",
        url=target_url,
        width=1280,
        height=800,
        min_size=(1024, 600),
        resizable=True
    )

    webview.start(icon=icon_path if icon_path and os.path.exists(icon_path) else None)
    sys.exit(0)

if __name__ == "__main__":
    main()
