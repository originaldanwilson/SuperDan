terraform {
  required_providers {
    fortios = {
      source  = "fortinetdev/fortios"
      version = "~> 1.20"
    }
  }
}

provider "fortios" {
  hostname = var.fortigate_hostname
  token    = var.fortigate_token
  insecure = true
}

variable "fortigate_hostname" {
  description = "FortiGate hostname or IP"
  type        = string
}

variable "fortigate_token" {
  description = "FortiGate API token"
  type        = string
  sensitive   = true
}

# SD-WAN Interface Members
resource "fortios_system_sdwan_members" "wan1" {
  interface = "wan1"
  gateway   = "192.168.1.1"
  priority  = 10
  weight    = 50
}

resource "fortios_system_sdwan_members" "wan2" {
  interface = "wan2"
  gateway   = "192.168.2.1"
  priority  = 20
  weight    = 50
}

# SD-WAN Health Check
resource "fortios_system_sdwan_healthcheck" "internet_check" {
  name     = "internet-health"
  server   = "8.8.8.8"
  protocol = "ping"
  interval = 5
  probe_timeout = 1000
  recoverytime  = 10

  members {
    seq_num = fortios_system_sdwan_members.wan1.seq_num
  }
  members {
    seq_num = fortios_system_sdwan_members.wan2.seq_num
  }
}

# SD-WAN Service Rule (Policy)
resource "fortios_system_sdwan_service" "critical_apps" {
  name     = "critical-apps-policy"
  mode     = "priority"
  priority = 1
  
  dst {
    name = "all"
  }

  src {
    name = "all"
  }

  # Application-based routing
  internet_service_app_ctrl = [123, 456]  # Office365, Salesforce app IDs
  
  # Performance SLA
  sla {
    health_check = fortios_system_sdwan_healthcheck.internet_check.name
    id           = 1
  }

  # Priority members
  priority_members {
    seq_num = fortios_system_sdwan_members.wan1.seq_num
  }
  priority_members {
    seq_num = fortios_system_sdwan_members.wan2.seq_num
  }

  # QoS settings
  tos      = "0x10"
  tos_mask = "0x3f"
}

# Firewall Policy to allow SD-WAN traffic
resource "fortios_firewall_policy" "sdwan_policy" {
  name   = "sdwan-outbound"
  action = "accept"
  
  srcintf {
    name = "internal"
  }

  dstintf {
    name = "virtual-wan-link"  # SD-WAN zone
  }

  srcaddr {
    name = "all"
  }

  dstaddr {
    name = "all"
  }

  service {
    name = "ALL"
  }

  schedule    = "always"
  nat         = "enable"
  logtraffic  = "all"
}

output "sdwan_service_id" {
  value = fortios_system_sdwan_service.critical_apps.id
}
