#!/bin/bash
"""
Installation script for pandas on RHEL8 with Python 3.13
Run this script on your target RHEL8 system after transferring the wheels directory
"""

echo "=== Pandas Installation for RHEL8 Python 3.13 ==="

# Check if Python 3.13 is available
if ! command -v python3.13 &> /dev/null; then
    echo "❌ python3.13 not found. Please install Python 3.13 first."
    exit 1
fi

echo "✅ Python 3.13 found: $(python3.13 --version)"

# Check if wheels directory exists
WHEELS_DIR="wheels_pandas_py312_compatible"
if [ ! -d "$WHEELS_DIR" ]; then
    echo "❌ Wheels directory '$WHEELS_DIR' not found."
    echo "   Please transfer the wheels directory to this location first."
    exit 1
fi

echo "✅ Wheels directory found: $WHEELS_DIR"

# Count wheel files
WHEEL_COUNT=$(find "$WHEELS_DIR" -name "*.whl" | wc -l)
echo "✅ Found $WHEEL_COUNT wheel files"

# Install packages in dependency order
echo ""
echo "Installing pandas dependencies..."

# Install basic dependencies first
echo "1. Installing six..."
python3.13 -m pip install --no-index --find-links "$WHEELS_DIR" six

echo "2. Installing pytz..."
python3.13 -m pip install --no-index --find-links "$WHEELS_DIR" pytz

echo "3. Installing tzdata..."
python3.13 -m pip install --no-index --find-links "$WHEELS_DIR" tzdata

echo "4. Installing python-dateutil..."
python3.13 -m pip install --no-index --find-links "$WHEELS_DIR" python-dateutil

echo "5. Installing numpy..."
python3.13 -m pip install --no-index --find-links "$WHEELS_DIR" numpy

echo "6. Installing pandas..."
python3.13 -m pip install --no-index --find-links "$WHEELS_DIR" pandas

echo ""
echo "=== Installation Complete ==="

# Test the installation
echo "Testing pandas import..."
if python3.13 -c "import pandas; print(f'✅ Pandas {pandas.__version__} installed successfully')" 2>/dev/null; then
    echo "🎉 Pandas installation successful!"
else
    echo "❌ Pandas installation failed or import error"
    echo "You may need to install additional system dependencies or compile from source"
    exit 1
fi

echo ""
echo "You can now use pandas in your Python 3.13 scripts!"
