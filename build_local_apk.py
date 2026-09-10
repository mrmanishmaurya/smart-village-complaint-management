import os
import sys
import socket
import subprocess
import shutil

APP_CONFIG_PATH = os.path.join(
    "android_app", "app", "src", "main", "java",
    "com", "smartvillage", "complaintmanagement", "AppConfig.java"
)
PROD_URL = "https://smart-village-complaint-management.onrender.com"

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "192.168.1.10"

def build_local_apk(custom_ip=None):
    lan_ip = custom_ip or get_lan_ip()
    local_url = f"http://{lan_ip}:5000"

    print("===================================================")
    print(" Building Android Local Test APK: SmartVillage_Local.apk")
    print(f" Target LAN Server: {local_url}")
    print("===================================================")

    if not os.path.exists(APP_CONFIG_PATH):
        print(f"Error: {APP_CONFIG_PATH} not found.")
        sys.exit(1)

    # Read original AppConfig content
    with open(APP_CONFIG_PATH, "r", encoding="utf-8") as f:
        original_content = f.read()

    try:
        # Update API_BASE_URL to local server URL
        modified_content = original_content.replace(PROD_URL, local_url)
        with open(APP_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(modified_content)

        print(f"1. Updated AppConfig.java API_BASE_URL to: {local_url}")

        # Run Gradle assembleDebug inside android_app
        print("2. Compiling Android Debug APK with Gradle...")
        cmd = ["cmd", "/c", "gradlew.bat assembleDebug"]
        res = subprocess.run(cmd, cwd="android_app")

        if res.returncode != 0:
            print("\nError: Gradle APK build failed.")
            sys.exit(1)

        # Copy built APK to root as SmartVillage_Local.apk
        built_apk = os.path.join("android_app", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
        output_local_apk = "SmartVillage_Local.apk"

        if os.path.exists(built_apk):
            shutil.copy(built_apk, output_local_apk)
            print("\n===================================================")
            print(" LOCAL ANDROID APK BUILD SUCCESSFUL!")
            print(f" Created: {os.path.abspath(output_local_apk)}")
            print(f" Connects to: {local_url}")
            print("===================================================")
        else:
            print(f"\nError: Built APK file not found at {built_apk}")
            sys.exit(1)

    finally:
        # ALWAYS restore AppConfig.java back to production default
        with open(APP_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(original_content)
        print("3. Restored AppConfig.java back to Production Render URL.")

if __name__ == "__main__":
    custom_ip = sys.argv[1] if len(sys.argv) > 1 else None
    build_local_apk(custom_ip)
