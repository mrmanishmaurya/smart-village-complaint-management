import os
import sys
import shutil
import zipfile
import subprocess

def create_installer_script():
    installer_code = '''import os
import sys
import shutil
import zipfile
import tempfile
import ctypes
import subprocess

APP_NAME = "Smart Village Complaint Management System"
EXE_NAME = "SmartVillage.exe"
ICON_NAME = "smart_village.ico"

def get_install_dir():
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(local_app_data, "SmartVillageApp")

def get_desktop_dir():
    try:
        import ctypes.wintypes
        CSIDL_DESKTOPDIRECTORY = 0x0010
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY, None, 0, buf) == 0:
            return buf.value
    except Exception:
        pass
    user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    return os.path.join(user_profile, "Desktop")

def get_start_menu_dir():
    try:
        import ctypes.wintypes
        CSIDL_PROGRAMS = 0x0002
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PROGRAMS, None, 0, buf) == 0:
            return buf.value
    except Exception:
        pass
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, r"Microsoft\\Windows\\Start Menu\\Programs")

def create_shortcut(target_exe, shortcut_path, icon_path):
    target_exe = os.path.abspath(target_exe)
    shortcut_path = os.path.abspath(shortcut_path)
    working_dir = os.path.dirname(target_exe)
    
    ps_cmd = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path}'); "
        f"$Shortcut.TargetPath = '{target_exe}'; "
        f"$Shortcut.WorkingDirectory = '{working_dir}'; "
        f"if (Test-Path '{icon_path}') {{ $Shortcut.IconLocation = '{icon_path}' }}; "
        f"$Shortcut.Save()"
    )
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        creationflags=creationflags,
        capture_output=True
    )

def run_installer():
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    
    # Path to embedded app zip payload
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    payload_zip = os.path.join(base_dir, "payload.zip")
    
    if os.path.exists(payload_zip):
        with zipfile.ZipFile(payload_zip, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
            
    target_exe = os.path.join(install_dir, EXE_NAME)
    icon_path = os.path.join(install_dir, ICON_NAME)
    if not os.path.exists(icon_path):
        icon_path = target_exe
        
    # Desktop Shortcut
    desktop = get_desktop_dir()
    desktop_shortcut = os.path.join(desktop, f"{APP_NAME}.lnk")
    create_shortcut(target_exe, desktop_shortcut, icon_path)
    
    # Start Menu Shortcut
    start_menu = get_start_menu_dir()
    app_start_dir = os.path.join(start_menu, APP_NAME)
    os.makedirs(app_start_dir, exist_ok=True)
    start_shortcut = os.path.join(app_start_dir, f"{APP_NAME}.lnk")
    create_shortcut(target_exe, start_shortcut, icon_path)
    
    # Uninstaller script
    uninstaller_path = os.path.join(install_dir, "uninstall.bat")
    with open(uninstaller_path, "w") as f:
        f.write(f'@echo off\\n')
        f.write(f'echo Uninstalling {APP_NAME}...\\n')
        f.write(f'if exist "{desktop_shortcut}" del "{desktop_shortcut}"\\n')
        f.write(f'if exist "{start_shortcut}" del "{start_shortcut}"\\n')
        f.write(f'if exist "{app_start_dir}" rmdir /s /q "{app_start_dir}"\\n')
        f.write(f'echo {APP_NAME} removed successfully.\\n')
        f.write(f'pause\\n')
        
    ctypes.windll.user32.MessageBoxW(
        0, 
        f"Installation completed successfully!\\n\\nApp installed to:\\n{install_dir}\\n\\nDesktop & Start Menu shortcuts created.", 
        APP_NAME, 
        0x40 | 0x0
    )

if __name__ == "__main__":
    run_installer()
'''

    with open("installer_runner.py", "w") as f:
        f.write(installer_code)

def main():
    print("===================================================")
    print(" Building Installer: SmartVillageSetup.exe")
    print("===================================================")

    if not os.path.exists("dist/SmartVillage"):
        print("Error: dist/SmartVillage build folder does not exist. Run PyInstaller first!")
        sys.exit(1)

    create_installer_script()

    # Step 1: Zip the dist/SmartVillage directory into payload.zip
    print("1. Packaging dist/SmartVillage into payload.zip...")
    payload_zip = "payload.zip"
    if os.path.exists(payload_zip):
        os.remove(payload_zip)

    with zipfile.ZipFile(payload_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("dist/SmartVillage"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, "dist/SmartVillage")
                zipf.write(file_path, arcname)

    # Step 2: Compile installer_runner.py into dist/SmartVillageSetup.exe using PyInstaller
    print("2. Compiling installer executable with PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon=smart_village.ico",
        "--add-data=payload.zip;.",
        "--add-data=smart_village.ico;.",
        "--name=SmartVillageSetup",
        "installer_runner.py"
    ]


    res = subprocess.run(cmd)
    
    # Cleanup temporary files
    if os.path.exists("payload.zip"):
        os.remove(payload_zip)
    if os.path.exists("installer_runner.py"):
        os.remove("installer_runner.py")
    if os.path.exists("installer_runner.spec"):
        os.remove("installer_runner.spec")

    if res.returncode == 0 and os.path.exists("dist/SmartVillageSetup.exe"):
        print("\n===================================================")
        print(" INSTALLER BUILD SUCCESSFUL!")
        print(" Installer created: dist\\SmartVillageSetup.exe")
        print("===================================================")
    else:
        print("\nInstaller build failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
