@echo off
REM Windows batch wrapper for PerfStack solution
REM This creates shortcuts/scripts to open PerfStack URLs

echo ======================================
echo SolarWinds PerfStack - Windows Edition
echo ======================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python and make sure it's in your PATH
    pause
    exit /b 1
)

REM Get user input
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

set /p HOURS="Hours to look back (default 168 = 7 days): "
if "%HOURS%"=="" set HOURS=168

echo.
echo Options:
echo 1. Open directly in browser (default)
echo 2. Create batch file for later use
echo 3. Create PowerShell script
echo 4. Create URL shortcut file
echo 5. Just save URL information
echo.

set /p CHOICE="Choose option (1-5): "
if "%CHOICE%"=="" set CHOICE=1

REM Build Python command
set PYTHON_CMD=python perfstack_windows.py --host "%HOST%" --interface "%INTERFACE%" --hours %HOURS%

if "%CHOICE%"=="1" (
    set PYTHON_CMD=%PYTHON_CMD% --open
    echo Opening in browser...
) else if "%CHOICE%"=="2" (
    set PYTHON_CMD=%PYTHON_CMD% --batch
    echo Creating batch file...
) else if "%CHOICE%"=="3" (
    set PYTHON_CMD=%PYTHON_CMD% --powershell
    echo Creating PowerShell script...
) else if "%CHOICE%"=="4" (
    set PYTHON_CMD=%PYTHON_CMD% --url-file
    echo Creating URL shortcut...
) else if "%CHOICE%"=="5" (
    set PYTHON_CMD=%PYTHON_CMD% --info-only
    echo Saving URL information...
) else (
    echo Invalid choice, using default (open in browser)
    set PYTHON_CMD=%PYTHON_CMD% --open
)

echo.
echo Running: %PYTHON_CMD%
echo.

REM Execute the Python script
%PYTHON_CMD%

if errorlevel 1 (
    echo.
    echo ERROR: Script failed
    pause
    exit /b 1
)

echo.
echo Done! Check the output above for next steps.
pause
