#!/bin/bash
# Installation script for Red Hat/CentOS/RHEL systems
# Run with: bash install_redhat.sh

set -e

echo "🔴 SolarWinds Scripts Installation for Red Hat/CentOS/RHEL"
echo "=========================================================="

# Check if we're running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
    echo "👤 Running with sudo (recommended)"
fi

# Detect package manager
if command -v dnf &> /dev/null; then
    PKG_MGR="dnf"
    echo "📦 Using dnf package manager"
elif command -v yum &> /dev/null; then
    PKG_MGR="yum"
    echo "📦 Using yum package manager"
else
    echo "❌ Neither dnf nor yum found. This script requires Red Hat-based system."
    exit 1
fi

# Install system dependencies
echo "🔧 Installing system dependencies..."
$SUDO $PKG_MGR install -y python3 python3-requests python3-urllib3

# Check if pip is available as a command
if command -v pip3 &> /dev/null; then
    echo "🐍 pip3 command found, using it"
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    echo "🐍 pip command found, using it"
    PIP_CMD="pip"
else
    echo "🐍 No pip command found, using python -m pip method"
    PIP_CMD="python -m pip"
fi

# Install tabulate (usually not available as system package on RHEL)
echo "📊 Installing tabulate for table formatting..."
if [[ "$PIP_CMD" == "python -m pip" ]]; then
    python -m pip install --user tabulate
else
    $PIP_CMD install --user tabulate
fi

# Test installation
echo "🧪 Testing installation..."
if python3 -c "from tabulate import tabulate; print('✅ tabulate OK')" 2>/dev/null; then
    echo "✅ tabulate installed successfully"
else
    echo "⚠️  tabulate installation may have issues, but continuing..."
fi

if python3 -c "import requests; print('✅ requests OK')" 2>/dev/null; then
    echo "✅ requests available"
else
    echo "❌ requests not available"
    exit 1
fi

# Make scripts executable if they exist
if [ -f "disr_dcsr_portchannel_monitor.py" ]; then
    chmod +x disr_dcsr_portchannel_monitor.py
    echo "✅ Made disr_dcsr_portchannel_monitor.py executable"
fi

if [ -f "run_disr_dcsr_report.py" ]; then
    chmod +x run_disr_dcsr_report.py
    echo "✅ Made run_disr_dcsr_report.py executable"
fi

if [ -f "solarwinds_interface_report.py" ]; then
    chmod +x solarwinds_interface_report.py
    echo "✅ Made solarwinds_interface_report.py executable"
fi

echo ""
echo "🎉 Installation completed successfully!"
echo ""
echo "📋 Quick test:"
echo "   python3 disr_dcsr_portchannel_monitor.py --help"
echo ""
echo "🚀 Usage example:"
echo "   python3 disr_dcsr_portchannel_monitor.py \\"
echo "       --server https://your-solarwinds-server.com \\"
echo "       --username your-username \\"
echo "       --password your-password"
echo ""
echo "🔒 For security, consider using environment variables:"
echo "   export SOLARWINDS_SERVER=https://your-server.com"
echo "   export SOLARWINDS_USERNAME=your-username"
echo "   export SOLARWINDS_PASSWORD=your-password"
echo "   python3 run_disr_dcsr_report.py"
echo ""
