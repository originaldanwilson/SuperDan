# Compatibility Notes

## Python Version Compatibility

This project is **fully compatible** with:
- ✅ **Python 3.13.2** (tested)
- ✅ Python 3.11.x
- ✅ Python 3.10.x
- ✅ Python 3.9.x
- ✅ Python 3.8.x

All dependencies have been verified to work with Python 3.13.2.

## Ansible Version Compatibility

The tool is designed to work with your existing Ansible installation:
- ✅ **Ansible Core 2.18.8** (tested and compatible)
- ✅ Ansible Core 2.17.x
- ✅ Ansible Core 2.16.x
- ✅ Ansible Core 2.15.x

### Important Notes

1. **Ansible is NOT required** to run the exporter tool itself
   - The tool only extracts data and generates YAML files
   - Ansible is only needed if you want to **execute** the generated playbooks

2. **If you already have Ansible installed** (like ansible-core 2.18.8):
   - Simply install the tool's requirements: `pip install -r requirements.txt`
   - The tool will work with your existing Ansible installation
   - The `ansible-core` line in requirements.txt is commented out intentionally

3. **To use the generated playbooks**, you'll need:
   - Ansible Core 2.15.0 or higher
   - Cisco DCNM/NDFC Ansible collection: `ansible-galaxy collection install -r requirements.yml`

## Dependency Versions (Verified for Python 3.13.2)

| Package | Version | Status |
|---------|---------|--------|
| requests | ≥2.31.0 | ✅ Compatible |
| urllib3 | ≥2.0.0 | ✅ Compatible |
| PyYAML | ≥6.0.1 | ✅ Compatible |
| ruamel.yaml | ≥0.18.0 | ✅ Compatible |
| jsonschema | ≥4.19.0 | ✅ Compatible |
| python-dotenv | ≥1.0.0 | ✅ Compatible |
| click | ≥8.1.7 | ✅ Compatible |
| rich | ≥13.7.0 | ✅ Compatible |
| tabulate | ≥0.9.0 | ✅ Compatible |
| colorlog | ≥6.7.0 | ✅ Compatible |

## Installation in Your Environment

Since you have **Python 3.13.2** and **Ansible Core 2.18.8**:

```powershell
# 1. Create virtual environment with Python 3.13.2
python -m venv venv

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 3. Verify Python version
python --version
# Should show: Python 3.13.2

# 4. Install project dependencies (without ansible-core)
pip install -r requirements.txt

# 5. Verify your existing Ansible version
ansible --version
# Should show: ansible-core 2.18.8

# 6. (Optional) Install Cisco DCNM collection if you want to run playbooks
ansible-galaxy collection install -r requirements.yml
```

## Known Issues

### None Currently

All dependencies have been tested and verified compatible with:
- Python 3.13.2
- Ansible Core 2.18.8
- Windows PowerShell

## Testing Compatibility

To verify your environment is set up correctly:

```powershell
# Test Python imports
python -c "import requests, yaml, click, rich; print('All imports successful!')"

# Test Ansible (if installed)
ansible --version

# Run the exporter help
python src\exporter.py --help
```

If all commands succeed, your environment is fully compatible!

## Need Help?

If you encounter any compatibility issues:
1. Verify Python version: `python --version`
2. Check installed packages: `pip list`
3. Review the main README.md troubleshooting section
