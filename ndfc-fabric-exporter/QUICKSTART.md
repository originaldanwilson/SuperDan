# Quick Start Guide

Get started with NDFC Fabric Exporter in 5 minutes!

## Quick Setup

### 1. Install Dependencies
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Python packages
pip install -r requirements.txt

# Install Ansible collections (optional, for running generated playbooks)
ansible-galaxy collection install -r requirements.yml
```

### 2. Configure Credentials
Copy and edit the configuration file:
```powershell
copy config.example.json config.json
```

Edit `config.json` with your NDFC details.

## Usage Examples

### List All Fabrics
```powershell
python src\exporter.py list-fabrics --host 10.0.0.1 --username admin
```

### Export a Fabric
```powershell
python src\exporter.py export `
  --host 10.0.0.1 `
  --username admin `
  --fabric MY_FABRIC `
  --output-dir output
```

### Export Using Config File
```powershell
python src\exporter.py export-from-config `
  --config-file config.json `
  --fabric MY_FABRIC
```

### Validate Generated Files
```powershell
python src\validator.py output
```

## What Gets Generated?

After running an export, you'll find these files in the `output/` directory:

- `inventory_*.yml` - Ansible inventory with all switches
- `fabric_config_*.yml` - Fabric configuration
- `vrf_config_*.yml` - VRF configurations  
- `network_config_*.yml` - Network/VLAN configurations
- `playbook_inventory_*.yml` - Complete playbook
- `fabric_data_*.json` - Raw JSON data from NDFC

## Next Steps

1. Review the generated YAML files
2. Modify them as needed for your use case
3. Use with Ansible to manage your fabric as code
4. Check the full README.md for advanced usage

## Troubleshooting

**SSL Errors?** Add `--no-verify-ssl` flag
**Auth Failed?** Check your credentials and NDFC accessibility
**Missing Data?** Verify your user has read permissions on NDFC

For more help, see README.md
