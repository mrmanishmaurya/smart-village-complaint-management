# Smart Village Complaint Management System - Desktop Software Guide

This guide explains how to build, install, run, and troubleshoot the Windows Desktop software version of the **Smart Village Complaint Management System**.

---

## 1. How to Build the Executable (.exe) & Installer

You can build the software automatically using the provided batch script:

### Option A: One-Click Build (Recommended)
Double-click `build_exe.bat` in the project root directory.

### Option B: Manual Command Line Build
Open PowerShell / Command Prompt in the project folder and run:

```cmd
# 1. Activate Virtual Environment
.\venv\Scripts\activate.bat

# 2. Install Required Dependencies
python -m pip install -r requirements.txt

# 3. Generate Application Icon
python generate_icon.py

# 4. Package Application with PyInstaller
python -m PyInstaller --clean SmartVillage.spec

# 5. Build Windows Setup Installer
python build_installer.py

# 6. Create Desktop Shortcut
powershell -NoProfile -ExecutionPolicy Bypass -File create_shortcut.ps1
```

---

## 2. Output File Locations

After a successful build, the generated files are located in:

- **Desktop Application Directory**: `dist\SmartVillage\SmartVillage.exe`
- **Windows Setup Installer**: `dist\SmartVillageSetup.exe`
- **Desktop Shortcut**: Created automatically on your Windows Desktop as `Smart Village Management.lnk`

---

## 3. How to Create / Re-Create the Desktop Shortcut

If you need to manually re-create the Desktop shortcut:

1. Double-click `create_shortcut.bat` in the project root folder.
   OR
2. Run PowerShell command:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File create_shortcut.ps1
   ```

Shortcut Details:
- **Name**: `Smart Village Management`
- **Target**: `dist\SmartVillage\SmartVillage.exe`
- **Icon**: `smart_village.ico`

---

## 4. How to Run the Software

### User Workflow:
1. Double-click the **Smart Village Management** Desktop Shortcut (or `dist\SmartVillage\SmartVillage.exe`).
2. The Flask backend starts silently in the background.
3. Your default web browser opens automatically to:
   `http://127.0.0.1:5000/smartvillage`
4. The system is ready to use for:
   - Citizen Registration & Login
   - Submitting Complaints & Uploading Images
   - Tracking Complaint Status
   - Admin Panel Management & Status Updates
   - Village Statistics & Category Overviews

---

## 5. Database Behavior (MySQL & Embedded SQLite)

- **Offline / Local Demo**: The application defaults to an embedded local SQLite database (`smart_village.db` stored in `%LOCALAPPDATA%\SmartVillage`). No database installation or setup is required on the target machine!
- **Cloud / Local MySQL**: If MySQL is available and configured via environment variables (`DB_TYPE=mysql`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`), the application connects to MySQL seamlessly.

---

## 6. Troubleshooting Common Errors

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Port 5000 already in use** | Another app is using port 5000. | `launcher.py` automatically detects free ports (e.g. 5001, 5002) and opens the browser on the available port. |
| **App already running message** | Another instance is active. | Check system taskbar or open `http://127.0.0.1:5000/smartvillage` directly. |
| **Image Upload Permission Error** | Writing to `C:\Program Files`. | Images are stored safely in `%LOCALAPPDATA%\SmartVillage\uploads` to avoid Windows security blocks. |
| **Missing Module Error during build** | `venv` dependencies not loaded. | Run `python -m pip install -r requirements.txt` before building. |
