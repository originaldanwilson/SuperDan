# NDFC Fabric Exporter

A Python tool to extract configuration from existing Cisco NDFC (Nexus Dashboard Fabric Controller) fabrics and generate Ansible-compatible YAML files for infrastructure as code management.

## Overview

This tool connects to your Cisco NDFC controller via REST API, extracts complete fabric configurations, and generates YAML files that can be used with Cisco's Ansible collections (cisco.dcnm) to recreate or manage your fabric as code.

## Features

- **Extract Complete Fabric Data**: Pulls fabric details, switches, VRFs, networks, and policies
- **Generate Ansible YAML**: Creates ready-to-use Ansible playbooks and variable files
- **Multiple Output Formats**: Saves both raw JSON data and structured YAML configs
- **CLI Interface**: Easy-to-use command-line tool with rich output formatting
- **Validation Ready**: Output format compatible with nac-validate and nac-test libraries

## Prerequisites

- Python 3.8 or higher
- Access to Cisco NDFC controller (REST API enabled)
- Valid NDFC credentials with read permissions

## Installation

### 1. Clone or Download the Project

```bash
cd C:\Users\danda\Documents\ndfc-fabric-exporter
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ansible Collections

```bash
ansible-galaxy collection install -r requirements.yml
```

## Configuration

### Option 1: Environment Variables

Copy the example environment file and configure:

```bash
copy .env.example .env
```

Edit `.env` with your NDFC details:

```
NDFC_HOST=10.0.0.1
NDFC_USERNAME=admin
NDFC_PASSWORD=your-password
NDFC_VERIFY_SSL=false
```

### Option 2: Configuration File

Copy the example config file:

```bash
copy config.example.json config.json
```

Edit `config.json` with your settings.

### Option 3: Command Line Arguments

Provide credentials directly via CLI (see usage below).

## Usage

### List Available Fabrics

```bash
python src/exporter.py list-fabrics --host 10.0.0.1 --username admin
```

### Export a Single Fabric

```bash
python src/exporter.py export \
  --host 10.0.0.1 \
  --username admin \
  --fabric FABRIC_NAME \
  --output-dir output
```

### Export Using Config File

```bash
python src/exporter.py export-from-config \
  --config-file config.json \
  --fabric FABRIC_NAME \
  --output-dir output
```

## Generated Files

The tool generates the following files in the output directory:

### 1. **inventory_[FABRIC_NAME].yml**
Ansible inventory file with all switches in the fabric

### 2. **fabric_config_[FABRIC_NAME].yml**
Fabric-level configuration for `cisco.dcnm.dcnm_fabric` module

### 3. **vrf_config_[FABRIC_NAME].yml**
VRF configurations for `cisco.dcnm.dcnm_vrf` module

### 4. **network_config_[FABRIC_NAME].yml**
Network/VLAN configurations for `cisco.dcnm.dcnm_network` module

### 5. **playbook_inventory_[FABRIC_NAME].yml**
Complete Ansible playbook for fabric inventory management

### 6. **fabric_data_[FABRIC_NAME].json** (optional)
Raw JSON data extracted from NDFC

## Using Generated Files with Ansible

### 1. Configure Ansible Connection

Create an `ansible.cfg` file:

```ini
[defaults]
inventory = output/inventory_FABRIC_NAME.yml
host_key_checking = False
timeout = 30

[inventory]
enable_plugins = yaml
```

### 2. Run Fabric Configuration

```bash
ansible-playbook output/playbook_inventory_FABRIC_NAME.yml \
  -e "ansible_connection=httpapi" \
  -e "ansible_httpapi_use_ssl=yes" \
  -e "ansible_httpapi_validate_certs=no" \
  -e "ansible_network_os=cisco.dcnm.dcnm" \
  -e "ansible_user=admin" \
  -e "ansible_password=password" \
  -e "ansible_host=10.0.0.1"
```

### 3. Apply Individual Configurations

```bash
# Apply fabric configuration
ansible-playbook output/fabric_config_FABRIC_NAME.yml

# Apply VRF configuration
ansible-playbook output/vrf_config_FABRIC_NAME.yml

# Apply network configuration
ansible-playbook output/network_config_FABRIC_NAME.yml
```

## Project Structure

```
ndfc-fabric-exporter/
├── src/
│   ├── __init__.py
│   ├── ndfc_client.py      # NDFC REST API client
│   ├── yaml_generator.py   # YAML file generator
│   └── exporter.py          # Main CLI tool
├── output/                  # Generated YAML files (created automatically)
├── templates/               # Custom Jinja2 templates (optional)
├── examples/                # Example configurations
├── tests/                   # Unit tests
├── docs/                    # Additional documentation
├── requirements.txt         # Python dependencies
├── requirements.yml         # Ansible collection requirements
├── config.example.json      # Example configuration file
├── .env.example             # Example environment variables
└── README.md                # This file
```

## Validation and Testing

The generated YAML files follow the Cisco Ansible NDFC collection schema and can be validated using:

### Using ansible-playbook --syntax-check

```bash
ansible-playbook output/playbook_inventory_FABRIC_NAME.yml --syntax-check
```

### Using ansible-lint

```bash
ansible-lint output/playbook_inventory_FABRIC_NAME.yml
```

### Using yamllint

```bash
yamllint output/*.yml
```

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL certificate validation errors, use the `--no-verify-ssl` flag:

```bash
python src/exporter.py export --host 10.0.0.1 --username admin --fabric FABRIC_NAME --no-verify-ssl
```

### Authentication Failures

- Verify your NDFC credentials
- Ensure the user has appropriate read permissions
- Check that the NDFC REST API is accessible

### Missing Data

Some fields may be empty if:
- The fabric doesn't have that resource type configured
- Your user doesn't have permissions to view certain resources
- The NDFC API version differs (check API endpoints in `ndfc_client.py`)

## Advanced Usage

### Custom Output Directory

```bash
python src/exporter.py export --fabric FABRIC_NAME --output-dir /path/to/custom/dir
```

### Export Multiple Fabrics

Create a script or use a loop:

```bash
for fabric in fabric1 fabric2 fabric3; do
  python src/exporter.py export --fabric $fabric --output-dir output/$fabric
done
```

### Integration with CI/CD

The tool can be integrated into CI/CD pipelines for automated fabric documentation or disaster recovery:

```yaml
# Example GitLab CI
export-fabric:
  script:
    - pip install -r requirements.txt
    - python src/exporter.py export --fabric PROD_FABRIC --output-dir artifacts
  artifacts:
    paths:
      - artifacts/
```

## API Compatibility

This tool is compatible with:
- Cisco NDFC 12.x
- Cisco DCNM 11.x (with possible API adjustments)

Refer to Cisco's NDFC REST API documentation for specific endpoint details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is provided as-is for use with Cisco NDFC environments.

## Related Resources

- [Cisco NDFC Documentation](https://www.cisco.com/c/en/us/support/cloud-systems-management/prime-data-center-network-manager/series.html)
- [cisco.dcnm Ansible Collection](https://galaxy.ansible.com/cisco/dcnm)
- [NDFC REST API Guide](https://developer.cisco.com/docs/nexus-dashboard-fabric-controller/)

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review the examples in the `examples/` directory
- Open an issue in the project repository

---

**Note**: Always test generated configurations in a non-production environment before applying to production fabrics.
