import os
import sys
import socket
import time
import threading
import webbrowser
import logging
from init_local_db import init_mysql

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [LOCAL_SERVER] %(message)s'
)
logger = logging.getLogger("LocalServer")

def get_lan_ip():
    """Detect local LAN IP address of this computer."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually send data, just finds routing interface
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def open_browser_delayed(url, delay=2.0):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"Could not automatically open browser: {e}")

def main():
    lan_ip = get_lan_ip()
    port = int(os.environ.get("PORT", 5000))
    local_pc_url = f"http://127.0.0.1:{port}/smartvillage"
    lan_mobile_url = f"http://{lan_ip}:{port}/smartvillage"

    print("\n" + "=" * 65)
    print(" SMART VILLAGE LOCAL SERVER STARTING UP...")
    print("=" * 65)

    # 1. Initialize local MySQL Database
    print("\n[STEP 1] Initializing Local MySQL Database ('smart_village')...")
    init_mysql()

    print("\n" + "=" * 65)
    print(" SMART VILLAGE LOCAL SERVER STARTED SUCCESSFULLY!")
    print("=" * 65)
    print(f" Local PC URL:       {local_pc_url}")
    print(f" Network/Mobile URL: {lan_mobile_url}")
    print(f" MySQL Database:     {os.environ.get('DB_NAME', 'smart_village')}")
    print("=" * 65)
    print(f" Connect your mobile phone or another laptop to the same Wi-Fi")
    print(f" and open: {lan_mobile_url}")
    print("=" * 65 + "\n")

    # 2. Open browser automatically
    threading.Thread(target=open_browser_delayed, args=(local_pc_url, 1.5), daemon=True).start()

    # 3. Start Flask server on 0.0.0.0:5000
    from app import app
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)

if __name__ == "__main__":
    main()
