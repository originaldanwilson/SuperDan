@echo off
REM DNS Query Tool Batch Wrapper for Windows
REM This batch file runs the Python DNS query tool on Windows systems

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.6 or later from https://python.org
    exit /b 1
)

REM Run the DNS query tool with all passed arguments
python "%~dp0dns_query_tool.py" %*