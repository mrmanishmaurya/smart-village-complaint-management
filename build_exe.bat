@echo off
echo ===================================================
echo   Smart Village Complaint Management System
echo   Building Desktop Executable (SmartVillage.exe)
echo ===================================================

IF EXIST venv\Scripts\activate.bat (
    echo Activating Virtual Environment...
    call venv\Scripts\activate.bat
)

echo Installing / Updating Required Dependencies...
python -m pip install -r requirements.txt

echo Generating Application Icon...
python generate_icon.py

echo Cleaning Previous Builds...
IF EXIST build rmdir /s /q build
IF EXIST dist rmdir /s /q dist

echo Running PyInstaller...
python -m PyInstaller --clean SmartVillage.spec

echo Building Installer Package (SmartVillageSetup.exe)...
python build_installer.py

echo Creating Desktop Shortcut (Smart Village Management)...
powershell -NoProfile -ExecutionPolicy Bypass -File create_shortcut.ps1

IF EXIST dist\SmartVillageSetup.exe (
    echo.
    echo ===================================================
    echo BUILD & PACKAGING SUCCESSFUL!
    echo Desktop App Directory: dist\SmartVillage\SmartVillage.exe
    echo Windows Setup Installer: dist\SmartVillageSetup.exe
    echo Desktop Shortcut Created: Smart Village Management
    echo ===================================================
) ELSE (
    echo.
    echo ===================================================
    echo BUILD COMPLETED with warnings. Check dist folder.
    echo ===================================================
)

pause
