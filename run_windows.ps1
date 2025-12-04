# Check if running as Admin (optional but recommended for winget)
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Warning "Not running as Administrator. Dependency installation (ffmpeg) might fail."
    Write-Warning "If you see errors, try right-clicking and 'Run as Administrator'."
}

# 1. Install Python Dependencies
Write-Host "--- Installing Python Dependencies ---" -ForegroundColor Cyan
try {
    pip install pynput
} catch {
    Write-Error "Failed to run pip. Is Python installed and added to PATH?"
    exit
}

# 2. Check FFmpeg
Write-Host "`n--- Checking FFmpeg ---" -ForegroundColor Cyan
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "FFmpeg is already installed." -ForegroundColor Green
} else {
    Write-Host "FFmpeg not found. Attempting to install via Winget..." -ForegroundColor Yellow
    try {
        winget install Gyan.FFmpeg
        Write-Host "FFmpeg installed via Winget. You may need to restart the computer for PATH changes to take effect." -ForegroundColor Green
        Write-Warning "If the script fails below, please restart this terminal/PowerShell window so the new PATH is loaded."
    } catch {
        Write-Error "Failed to install FFmpeg automatically."
        Write-Host "Please install FFmpeg manually: https://ffmpeg.org/download.html"
    }
}

# 3. Run the Recorder
Write-Host "`n--- Starting Recorder ---" -ForegroundColor Cyan
$ScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "capture_data_windows.py"

if (Test-Path $ScriptPath) {
    python $ScriptPath
} else {
    Write-Error "Could not find capture_data_windows.py in this folder: $PSScriptRoot"
}

Write-Host "`nRecorder finished." -ForegroundColor Green
Read-Host -Prompt "Press Enter to exit"
