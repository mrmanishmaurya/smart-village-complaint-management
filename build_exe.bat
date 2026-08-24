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

IF EXIST dist\SmartVillage.exe (
    echo.
    echo ===================================================
    echo BUILD SUCCESSFUL!
    echo Final Executable Created: dist\SmartVillage.exe
    echo ===================================================
) ELSE (
    echo.
    echo ===================================================
    echo BUILD FAILED! Check error messages above.
    echo ===================================================
)

pause
