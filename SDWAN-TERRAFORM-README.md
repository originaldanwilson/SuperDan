# SD-WAN Terraform Policy Configurations

This directory contains Terraform configurations for deploying SD-WAN policies on two platforms: FortiOS and Prisma SD-WAN.

## FortiOS SD-WAN Policy (`fortios-sdwan-policy.tf`)

Uses the native FortiOS provider with:
- Dual WAN interfaces with health checks
- SD-WAN service rule for application-aware routing
- Performance SLA monitoring
- Firewall policy with NAT

**Status**: Production-ready

## Prisma SD-WAN Policy (`prisma-sdwan-policy.tf`)

Uses REST API provider (no native provider exists) with:
- WAN path configuration
- Custom app definitions
- QoS, security, and path policies
- Site-level policy binding

**Status**: Requires API endpoint/token from your Prisma Access console and may need field adjustments based on your API version.

## Usage

### FortiOS
```bash
terraform init
terraform plan -var="fortigate_hostname=YOUR_HOST" -var="fortigate_token=YOUR_TOKEN"
terraform apply
```

### Prisma SD-WAN
```bash
terraform init
terraform plan -var="prisma_api_url=YOUR_API_URL" -var="prisma_auth_token=YOUR_TOKEN" -var="site_id=YOUR_SITE_ID"
terraform apply
```
