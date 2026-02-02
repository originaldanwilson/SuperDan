"""
YAML Generator for converting NDFC fabric data to Ansible-compatible YAML files.
"""

import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


class AnsibleYAMLGenerator:
    """Generate Ansible-compatible YAML files from NDFC fabric data."""
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize YAML generator.
        
        Args:
            output_dir: Directory to save generated YAML files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=2, offset=2)
        
    def generate_inventory(self, fabric_data: Dict[str, Any]) -> str:
        """
        Generate Ansible inventory file from fabric data.
        
        Args:
            fabric_data: Complete fabric data dictionary
            
        Returns:
            Path to generated inventory file
        """
        fabric_name = fabric_data.get("fabric_name", "unknown_fabric")
        switches = fabric_data.get("switches", [])
        
        inventory = {
            "all": {
                "children": {
                    "ndfc": {
                        "children": {
                            fabric_name: {
                                "hosts": {}
                            }
                        }
                    }
                }
            }
        }
        
        # Add switches to inventory
        for switch in switches:
            switch_name = switch.get("logicalName") or switch.get("serialNumber")
            switch_ip = switch.get("ipAddress") or switch.get("managementIP")
            
            if switch_name:
                inventory["all"]["children"]["ndfc"]["children"][fabric_name]["hosts"][switch_name] = {
                    "ansible_host": switch_ip,
                    "serial_number": switch.get("serialNumber"),
                    "model": switch.get("model"),
                    "role": switch.get("switchRole")
                }
        
        output_file = self.output_dir / f"inventory_{fabric_name}.yml"
        
        with open(output_file, 'w') as f:
            self.yaml.dump(inventory, f)
        
        logger.info(f"Generated inventory file: {output_file}")
        return str(output_file)
    
    def generate_fabric_config(self, fabric_data: Dict[str, Any]) -> str:
        """
        Generate fabric configuration YAML for cisco.dcnm.dcnm_fabric module.
        
        Args:
            fabric_data: Complete fabric data dictionary
            
        Returns:
            Path to generated fabric config file
        """
        fabric_name = fabric_data.get("fabric_name", "unknown_fabric")
        fabric_details = fabric_data.get("fabric_details", {})
        
        fabric_config = {
            "fabric_name": fabric_name,
            "fabric_type": fabric_details.get("fabricType", "VXLAN_EVPN"),
            "fabric_template": fabric_details.get("templateName", "Easy_Fabric"),
            "fabric_settings": {}
        }
        
        # Extract fabric settings
        if "nvPairs" in fabric_details:
            fabric_config["fabric_settings"] = fabric_details["nvPairs"]
        
        ansible_task = {
            "name": f"Configure NDFC Fabric {fabric_name}",
            "cisco.dcnm.dcnm_fabric": {
                "state": "merged",
                "config": [fabric_config]
            }
        }
        
        output_file = self.output_dir / f"fabric_config_{fabric_name}.yml"
        
        with open(output_file, 'w') as f:
            self.yaml.dump([ansible_task], f)
        
        logger.info(f"Generated fabric config file: {output_file}")
        return str(output_file)
    
    def generate_vrf_config(self, fabric_data: Dict[str, Any]) -> str:
        """
        Generate VRF configuration YAML for cisco.dcnm.dcnm_vrf module.
        
        Args:
            fabric_data: Complete fabric data dictionary
            
        Returns:
            Path to generated VRF config file
        """
        fabric_name = fabric_data.get("fabric_name", "unknown_fabric")
        vrfs = fabric_data.get("vrfs", [])
        
        vrf_configs = []
        
        for vrf in vrfs:
            vrf_config = {
                "fabric": fabric_name,
                "vrf_name": vrf.get("vrfName"),
                "vrf_id": vrf.get("vrfId"),
                "vlan_id": vrf.get("vlanId"),
                "vrf_template": vrf.get("vrfTemplate", "Default_VRF_Universal"),
                "vrf_extension_template": vrf.get("vrfExtensionTemplate", "Default_VRF_Extension_Universal"),
                "attach": []
            }
            
            # Add VRF attachments if available
            if "attachments" in vrf:
                for attach in vrf["attachments"]:
                    vrf_config["attach"].append({
                        "ip_address": attach.get("ipAddress"),
                        "deploy": attach.get("isAttached", True)
                    })
            
            vrf_configs.append(vrf_config)
        
        ansible_task = {
            "name": f"Configure VRFs for fabric {fabric_name}",
            "cisco.dcnm.dcnm_vrf": {
                "state": "merged",
                "fabric": fabric_name,
                "config": vrf_configs
            }
        }
        
        output_file = self.output_dir / f"vrf_config_{fabric_name}.yml"
        
        with open(output_file, 'w') as f:
            self.yaml.dump([ansible_task], f)
        
        logger.info(f"Generated VRF config file: {output_file}")
        return str(output_file)
    
    def generate_network_config(self, fabric_data: Dict[str, Any]) -> str:
        """
        Generate network/VLAN configuration YAML for cisco.dcnm.dcnm_network module.
        
        Args:
            fabric_data: Complete fabric data dictionary
            
        Returns:
            Path to generated network config file
        """
        fabric_name = fabric_data.get("fabric_name", "unknown_fabric")
        networks = fabric_data.get("networks", [])
        
        network_configs = []
        
        for network in networks:
            network_config = {
                "fabric": fabric_name,
                "net_name": network.get("networkName"),
                "net_id": network.get("networkId"),
                "vrf_name": network.get("vrfName"),
                "vlan_id": network.get("vlanId"),
                "gw_ip_subnet": network.get("gatewayIpAddress"),
                "net_template": network.get("networkTemplate", "Default_Network_Universal"),
                "net_extension_template": network.get("networkExtensionTemplate", "Default_Network_Extension_Universal"),
                "attach": []
            }
            
            # Add network attachments if available
            if "attachments" in network:
                for attach in network["attachments"]:
                    network_config["attach"].append({
                        "ip_address": attach.get("ipAddress"),
                        "ports": attach.get("switchPorts", []),
                        "deploy": attach.get("isAttached", True)
                    })
            
            network_configs.append(network_config)
        
        ansible_task = {
            "name": f"Configure Networks for fabric {fabric_name}",
            "cisco.dcnm.dcnm_network": {
                "state": "merged",
                "fabric": fabric_name,
                "config": network_configs
            }
        }
        
        output_file = self.output_dir / f"network_config_{fabric_name}.yml"
        
        with open(output_file, 'w') as f:
            self.yaml.dump([ansible_task], f)
        
        logger.info(f"Generated network config file: {output_file}")
        return str(output_file)
    
    def generate_inventory_playbook(self, fabric_data: Dict[str, Any]) -> str:
        """
        Generate Ansible playbook for fabric inventory management.
        
        Args:
            fabric_data: Complete fabric data dictionary
            
        Returns:
            Path to generated playbook file
        """
        fabric_name = fabric_data.get("fabric_name", "unknown_fabric")
        switches = fabric_data.get("switches", [])
        
        switch_configs = []
        
        for switch in switches:
            switch_config = {
                "seed_ip": switch.get("ipAddress"),
                "auth_proto": "MD5",
                "max_hops": 0,
                "role": switch.get("switchRole", "leaf"),
                "preserve_config": False
            }
            switch_configs.append(switch_config)
        
        playbook = [{
            "name": f"Manage NDFC Fabric Inventory - {fabric_name}",
            "hosts": "localhost",
            "gather_facts": False,
            "tasks": [{
                "name": f"Add switches to fabric {fabric_name}",
                "cisco.dcnm.dcnm_inventory": {
                    "fabric": fabric_name,
                    "state": "merged",
                    "config": switch_configs
                }
            }]
        }]
        
        output_file = self.output_dir / f"playbook_inventory_{fabric_name}.yml"
        
        with open(output_file, 'w') as f:
            self.yaml.dump(playbook, f)
        
        logger.info(f"Generated inventory playbook: {output_file}")
        return str(output_file)
    
    def generate_all(self, fabric_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate all YAML configuration files for a fabric.
        
        Args:
            fabric_data: Complete fabric data dictionary
            
        Returns:
            Dictionary mapping config type to file path
        """
        generated_files = {}
        
        logger.info(f"Generating all YAML files for fabric: {fabric_data.get('fabric_name')}")
        
        generated_files["inventory"] = self.generate_inventory(fabric_data)
        generated_files["fabric_config"] = self.generate_fabric_config(fabric_data)
        generated_files["vrf_config"] = self.generate_vrf_config(fabric_data)
        generated_files["network_config"] = self.generate_network_config(fabric_data)
        generated_files["inventory_playbook"] = self.generate_inventory_playbook(fabric_data)
        
        logger.info(f"Generated {len(generated_files)} YAML files")
        return generated_files
