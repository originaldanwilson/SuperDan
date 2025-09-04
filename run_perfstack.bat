@echo off
REM Simple PerfStack Windows Runner
REM Run this from the same directory as perfstack_windows.py

echo ========================================
echo SolarWinds PerfStack - Windows Runner
echo ========================================
echo.

REM Change to the directory where this batch file is located
cd /d "%~dp0"

REM Show current directory
echo Current directory: %CD%
echo.

REM Check if Python script exists in current directory
if not exist "perfstack_windows.py" (
    echo ERROR: perfstack_windows.py not found in current directory
    echo Please make sure this batch file is in the same folder as perfstack_windows.py
    echo.
    echo Files in current directory:
    dir *.py
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

echo Python found and script exists in current directory
echo.

REM Get input from user
set /p HOST="Enter device hostname or IP: "
if "%HOST%"=="" (
    echo ERROR: Hostname is required
    pause
    exit /b 1
)

set /p INTERFACE="Enter interface name (e.g., Gi0/1, Po5): "
if "%INTERFACE%"=="" (
    echo ERROR: Interface is required
    pause
    exit /b 1
)

echo.
echo Quick options:
echo 1. Open in browser now (recommended)
echo 2. Create batch file for later
echo 3. Create URL shortcut
echo 4. Just show me the URL
echo.

set /p CHOICE="Choose (1-4, default=1): "
if "%CHOICE%"=="" set CHOICE=1

REM Run the Python script with current directory
if "%CHOICE%"=="1" (
    echo Opening in browser...
    python perfstack_windows.py --host "%HOST%" --interface "%INTERFACE%" --open
) else if "%CHOICE%"=="2" (
    echo Creating batch file...
    python perfstack_windows.py --host "%HOST%" --interface "%INTERFACE%" --batch
) else if "%CHOICE%"=="3" (
    echo Creating URL shortcut...
    python perfstack_windows.py --host "%HOST%" --interface "%INTERFACE%" --url-file
) else if "%CHOICE%"=="4" (
    echo Getting URL info...
    python perfstack_windows.py --host "%HOST%" --interface "%INTERFACE%" --info-only
) else (
    echo Invalid choice, opening in browser...
    python perfstack_windows.py --host "%HOST%" --interface "%INTERFACE%" --open
)

if errorlevel 1 (
    echo.
    echo ERROR: Script failed - check the error messages above
    pause
    exit /b 1
)

echo.
echo Success! Check the output above for next steps.
echo.
pause
