terraform {
  required_providers {
    restapi = {
      source  = "Mastercard/restapi"
      version = "~> 1.18"
    }
  }
}

provider "restapi" {
  uri                  = var.prisma_api_url
  write_returns_object = true
  
  headers = {
    "X-Auth-Token" = var.prisma_auth_token
    "Content-Type" = "application/json"
  }
}

variable "prisma_api_url" {
  description = "Prisma SD-WAN API URL (e.g., https://api.sase.paloaltonetworks.com)"
  type        = string
}

variable "prisma_auth_token" {
  description = "Prisma SD-WAN authentication token"
  type        = string
  sensitive   = true
}

variable "site_id" {
  description = "Site ID for the policy"
  type        = string
}

# Path (WAN Link) Configuration
resource "restapi_object" "wan_paths" {
  path = "/sdwan/v4.9/api/sites/${var.site_id}/waninterfaces"
  data = jsonencode({
    name        = "primary-wan"
    type        = "publicwan"
    link_bw_down = 100
    link_bw_up   = 100
    network_id   = "internet"
  })
}

resource "restapi_object" "secondary_wan" {
  path = "/sdwan/v4.9/api/sites/${var.site_id}/waninterfaces"
  data = jsonencode({
    name        = "secondary-wan"
    type        = "publicwan"
    link_bw_down = 50
    link_bw_up   = 50
    network_id   = "internet"
  })
}

# Application Definition
resource "restapi_object" "critical_app" {
  path = "/sdwan/v4.9/api/appdefs"
  data = jsonencode({
    name        = "critical-business-apps"
    description = "Mission critical applications"
    app_type    = "custom"
    domains     = ["salesforce.com", "office365.com"]
  })
}

# QoS Policy Profile
resource "restapi_object" "qos_profile" {
  path = "/sdwan/v4.9/api/networkpolicysetstacks"
  data = jsonencode({
    name = "critical-apps-qos"
    policyrules = [{
      name        = "prioritize-critical"
      app_def_ids = [jsondecode(restapi_object.critical_app.api_response).id]
      paths_allowed = ["any"]
      service_context = {
        type        = "qos"
        bandwidth   = "guaranteed"
        priority    = 1
      }
    }]
  })
}

# Security Policy
resource "restapi_object" "security_policy" {
  path = "/sdwan/v4.9/api/securitypolicysets"
  data = jsonencode({
    name = "sdwan-security-policy"
    policyrules = [{
      name        = "allow-critical-apps"
      action      = "allow"
      source_zone = "LAN"
      destination_zone = "WAN"
      app_def_ids = [jsondecode(restapi_object.critical_app.api_response).id]
      services    = ["HTTPS", "HTTP"]
      enabled     = true
    }]
  })
}

# Path Policy (SD-WAN routing decision)
resource "restapi_object" "path_policy" {
  path = "/sdwan/v4.9/api/networkpolicysetstacks"
  data = jsonencode({
    name = "app-aware-routing"
    policyrules = [{
      name        = "route-critical-apps"
      app_def_ids = [jsondecode(restapi_object.critical_app.api_response).id]
      paths_allowed = [
        jsondecode(restapi_object.wan_paths.api_response).id,
        jsondecode(restapi_object.secondary_wan.api_response).id
      ]
      path_selection_mode = "ordered"  # Primary then secondary
      service_context = {
        active_sla_probe   = true
        sla_probe_profile  = "low-latency"
      }
    }]
  })
}

# Bind policies to site
resource "restapi_object" "site_policy_binding" {
  path = "/sdwan/v4.9/api/sites/${var.site_id}/ngfwsecuritypolicysetstacks"
  data = jsonencode({
    security_policyset_id = jsondecode(restapi_object.security_policy.api_response).id
    network_policyset_id  = jsondecode(restapi_object.path_policy.api_response).id
  })
}

output "policy_ids" {
  value = {
    path_policy     = jsondecode(restapi_object.path_policy.api_response).id
    security_policy = jsondecode(restapi_object.security_policy.api_response).id
    qos_profile     = jsondecode(restapi_object.qos_profile.api_response).id
  }
}
