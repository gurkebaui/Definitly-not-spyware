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
    } catch {
        Write-Error "Failed to install FFmpeg automatically."
        Write-Host "Please install FFmpeg manually: https://ffmpeg.org/download.html"
    }
}

# 3. Setup Auto-Start
Write-Host "`n--- Configuring Auto-Start ---" -ForegroundColor Cyan

# Get absolute paths
$ScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "capture_data_windows.py"

# Check if the python script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Could not find capture_data_windows.py in this folder: $PSScriptRoot"
    exit
}

# Find Python executable
$PythonPath = (Get-Command python).Source
if (-not $PythonPath) {
    Write-Error "Could not find 'python' executable."
    exit
}

# Startup Folder Path
$StartupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = "$StartupDir\ChimeraRecorder.lnk"

try {
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonPath
    # Arguments: The script path. We wrap it in quotes to handle spaces.
    $Shortcut.Arguments = """$ScriptPath"""
    $Shortcut.WorkingDirectory = $PSScriptRoot
    $Shortcut.Description = "Chimera Data Recorder Auto-Start"
    $Shortcut.WindowStyle = 7 # 7 = Minimized/MinimizedNoFocus (keeps it out of the way)
    $Shortcut.Save()
    
    Write-Host "Success! Shortcut created at: $ShortcutPath" -ForegroundColor Green
    Write-Host "The recorder will now start automatically when you log in."
} catch {
    Write-Error "Failed to create startup shortcut: $_"
}

Write-Host "`nSetup finished." -ForegroundColor Green
Read-Host -Prompt "Press Enter to exit"
