# SolarWinds PerfStack PowerShell Runner
# More reliable than batch files on modern Windows

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SolarWinds PerfStack - PowerShell Runner" -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Script directory: $ScriptDir" -ForegroundColor Yellow
Write-Host ""

# Check if Python script exists
$PythonScript = Join-Path $ScriptDir "perfstack_windows.py"
if (-not (Test-Path $PythonScript)) {
    Write-Host "ERROR: perfstack_windows.py not found in script directory" -ForegroundColor Red
    Write-Host "Please make sure perfstack_windows.py is in the same folder as this script" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Python files in current directory:" -ForegroundColor Yellow
    Get-ChildItem -Path $ScriptDir -Filter "*.py" | Format-Table Name, Length, LastWriteTime
    Read-Host "Press Enter to exit"
    exit 1
}

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python or add it to your PATH" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# Get user input
do {
    $Host_Input = Read-Host "Enter device hostname or IP"
} while ([string]::IsNullOrWhiteSpace($Host_Input))

do {
    $Interface = Read-Host "Enter interface name (e.g., Gi0/1, Po5)"
} while ([string]::IsNullOrWhiteSpace($Interface))

Write-Host ""
Write-Host "Quick options:" -ForegroundColor Cyan
Write-Host "1. Open in browser now (recommended)" -ForegroundColor White
Write-Host "2. Create batch file for later use" -ForegroundColor White
Write-Host "3. Create URL shortcut file" -ForegroundColor White
Write-Host "4. Just show me the URL" -ForegroundColor White
Write-Host ""

$Choice = Read-Host "Choose (1-4, default=1)"
if ([string]::IsNullOrWhiteSpace($Choice)) { $Choice = "1" }

# Build and execute Python command
$PythonArgs = @("perfstack_windows.py", "--host", $Host_Input, "--interface", $Interface)

switch ($Choice) {
    "1" { 
        Write-Host "🌐 Opening in browser..." -ForegroundColor Green
        $PythonArgs += "--open"
    }
    "2" { 
        Write-Host "📝 Creating batch file..." -ForegroundColor Green
        $PythonArgs += "--batch"
    }
    "3" { 
        Write-Host "🔗 Creating URL shortcut..." -ForegroundColor Green
        $PythonArgs += "--url-file"
    }
    "4" { 
        Write-Host "📄 Getting URL info..." -ForegroundColor Green
        $PythonArgs += "--info-only"
    }
    default { 
        Write-Host "🌐 Invalid choice, opening in browser..." -ForegroundColor Yellow
        $PythonArgs += "--open"
    }
}

Write-Host ""
Write-Host "Running: python $($PythonArgs -join ' ')" -ForegroundColor Cyan
Write-Host ""

# Execute the Python script
try {
    $result = & python @PythonArgs
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "✅ Success! Check the output above for next steps." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "❌ Script failed with exit code: $exitCode" -ForegroundColor Red
        Write-Host "Check the error messages above" -ForegroundColor Yellow
    }
}
catch {
    Write-Host ""
    Write-Host "❌ ERROR: Failed to run Python script" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Press Enter to exit"
