# PowerShell Script to create Desktop Shortcut for Smart Village Management

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "Smart Village Management.lnk"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$TargetExe = Join-Path -Path $ScriptDir -ChildPath "dist\SmartVillage\SmartVillage.exe"
$IconPath = Join-Path -Path $ScriptDir -ChildPath "smart_village.ico"

if (-not (Test-Path $TargetExe)) {
    # Fallback to single exe if present
    $TargetExeSingle = Join-Path -Path $ScriptDir -ChildPath "dist\SmartVillage.exe"
    if (Test-Path $TargetExeSingle) {
        $TargetExe = $TargetExeSingle
    }
}

if (Test-Path $TargetExe) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.WorkingDirectory = Split-Path -Parent $TargetExe
    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = $IconPath
    }
    $Shortcut.Description = "Smart Village Complaint Management System"
    $Shortcut.Save()
    Write-Host "SUCCESS: Desktop shortcut created at: $ShortcutPath" -ForegroundColor Green
} else {
    Write-Host "ERROR: Could not find SmartVillage.exe in dist folder. Please build the application first." -ForegroundColor Red
}
