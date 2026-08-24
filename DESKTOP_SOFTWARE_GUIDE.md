# Smart Village Complaint Management System - Desktop Software Guide

Welcome to the **Smart Village Complaint Management System** Windows Desktop Software setup and deployment guide. This document explains how the Flask web application has been converted into a native Windows desktop software application (`SmartVillage.exe`), how to run it in development, how to build the executable, and how to create a setup installer.

---

## 1. Project Overview & Desktop Architecture

The application has been converted into a standalone desktop application using a 3-tier desktop architecture:

```
[ PyWebView GUI Window ]
          │
          ▼  (Embedded Local HTTP)
[ Flask Backend Server (localhost) ]
          │
          ▼  (Dual DB Adapter)
[ MySQL Server OR Portable SQLite Database ]
```

### Key Highlights:
- **No Terminal Window Required**: Double-clicking `SmartVillage.exe` launches the desktop window directly.
- **Automatic Port Allocation**: Finds an available local HTTP port dynamically (starting at port 5000).
- **Windows Installation & Permission Safety**: Never attempts to write inside `C:\Program Files (x86)\SmartVillage` or bundled static folders. All user-writable data (uploaded complaint photos and SQLite database) is stored safely inside `%LOCALAPPDATA%\SmartVillage`.
- **Plug-and-Play Dual Database**: Supports MySQL via `.env` credentials, and automatically falls back to a portable SQLite database (`smart_village.db`) in `%LOCALAPPDATA%\SmartVillage` if MySQL is not installed or running.
- **Resource Resolution**: Templates, static assets, and database schemas are bundled inside the executable via `sys._MEIPASS` (read-only).

---

## 2. How to Run in Development Mode

To test or run the application in development:

1. Open PowerShell or Command Prompt in the project folder.
2. Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the desktop launcher:
   ```bash
   python desktop_app.py
   ```
4. The native desktop window will open automatically, loading the Smart Village Complaint Management System interface (`http://127.0.0.1:<PORT>/smartvillage`).

---

## 3. How to Build `SmartVillage.exe`

You can build the executable in two ways:

### Option A: Using the Automated Batch Script (Recommended)
Double-click `build_exe.bat` or run in Command Prompt:
```cmd
build_exe.bat
```

### Option B: Manual Command
Run PyInstaller using the project specification file:
```bash
python -m PyInstaller --clean SmartVillage.spec
```

---

## 4. Location of the Output Executable

After a successful build, the generated executable is located at:

```
dist/SmartVillage.exe
```

Double-clicking `dist/SmartVillage.exe` will run the standalone desktop application without needing Python installed on the machine.

---

## 5. Database Configuration & Production Strategy

### MySQL Mode (Development & Centralized Server)
- Database credentials are managed via the `.env` file:
  ```env
  DB_HOST=localhost
  DB_USER=root
  DB_PASSWORD=YourPasswordHere
  DB_NAME=smart_village
  DB_TYPE=mysql
  ```
- **Security**: Never commit `.env` or hardcode database passwords in source code.

### SQLite Desktop Mode (Standalone & Portable)
- If MySQL server is offline or not installed on the user's PC, the application automatically uses a local SQLite database (`smart_village.db`).
- All tables (`users`, `admins`, `categories`, `complaints`, `feedback`) and default seed data (categories & admin account) are auto-created on first run.

---

## 6. How to Create the Windows Installer (`SmartVillage_Setup.exe`)

To package `SmartVillage.exe` into an installer wizard:

1. Download and install **[Inno Setup](https://jrsoftware.org/isinfo.php)** (free).
2. Open `SmartVillage_Setup.iss` in Inno Setup Compiler.
3. Click **Compile** (or press `Ctrl + F9`).
4. The output installer will be generated at:
   ```
   installer_output/SmartVillage_Setup.exe
   ```

### Features of the Installer:
- Standard Windows Installation Wizard.
- Creates Start Menu shortcut.
- Creates Desktop shortcut.
- Includes uninstaller.
- Auto-launches application after setup completes.

---

## 7. Software Distribution

To distribute the application to other Windows computers:
- **Option 1 (Simple)**: Share the `dist/SmartVillage.exe` file directly.
- **Option 2 (Professional)**: Share the `installer_output/SmartVillage_Setup.exe` installer file.

Neither option requires the target machine to have Python, Flask, or MySQL pre-installed.

---

## 8. Common Errors & Troubleshooting

| Error / Symptom | Possible Cause | Solution |
| :--- | :--- | :--- |
| **MySQL Connection Error** | MySQL server is stopped or credentials in `.env` are invalid. | The app will automatically switch to portable SQLite mode. To use MySQL, start MySQL service in XAMPP / MySQL Workbench and verify `.env` values. |
| **Window stays blank on launch** | Port conflict or firewall blocking localhost socket. | The launcher automatically tries ports 5000-5099. Ensure local antivirus allows localhost connections. |
| **Image Upload fails** | Missing permissions or invalid path. | The app auto-creates `%LOCALAPPDATA%\SmartVillage\uploads`. Ensure user profile directory is accessible. |
| **PyInstaller build error** | Outdated packages or lock files. | Run `build_exe.bat` which performs `--clean` build. |

---

## 9. Included File Reference

- `desktop_app.py` - Desktop GUI launcher (`pywebview` wrapper).
- `app.py` - Main Flask application with dual database adapter & path resolution.
- `generate_icon.py` - Icon generator script for `smart_village.ico`.
- `smart_village.ico` - Application icon file.
- `SmartVillage.spec` - PyInstaller build configuration.
- `build_exe.bat` - Automated build script for `dist/SmartVillage.exe`.
- `SmartVillage_Setup.iss` - Inno Setup installer script for setup wizard.
- `requirements.txt` - Python project dependencies.
