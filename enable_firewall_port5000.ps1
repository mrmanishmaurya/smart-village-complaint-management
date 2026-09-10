# PowerShell script to allow Inbound TCP Port 5000 on Private Networks for Smart Village Local Server

$ruleName = "Smart Village Local Server (TCP 5000)"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "SUCCESS: Windows Firewall rule '$ruleName' is already configured." -ForegroundColor Green
} else {
    Write-Host "Adding Windows Firewall Inbound Rule for TCP Port 5000 (Private Profile)..." -ForegroundColor Yellow
    try {
        New-NetFirewallRule -DisplayName $ruleName `
                            -Direction Inbound `
                            -LocalPort 5000 `
                            -Protocol TCP `
                            -Profile Private `
                            -Action Allow `
                            -ErrorAction Stop
        Write-Host "SUCCESS: Windows Firewall rule '$ruleName' added successfully." -ForegroundColor Green
    } catch {
        Write-Host "NOTICE: Could not automatically add firewall rule (requires Administrator privileges)." -ForegroundColor Red
        Write-Host "To manually allow Port 5000 on LAN, open PowerShell as Administrator and run:" -ForegroundColor Yellow
        Write-Host "New-NetFirewallRule -DisplayName '$ruleName' -Direction Inbound -LocalPort 5000 -Protocol TCP -Profile Private -Action Allow" -ForegroundColor Cyan
    }
}
