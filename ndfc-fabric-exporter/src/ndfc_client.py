"""
NDFC API Client for extracting fabric configuration data.
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


class NDFCClient:
    """Client for interacting with Cisco NDFC REST API."""
    
    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = False):
        """
        Initialize NDFC client.
        
        Args:
            host: NDFC controller hostname or IP
            username: NDFC username
            password: NDFC password
            verify_ssl: Whether to verify SSL certificates
        """
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.token = None
        self.base_url = f"https://{self.host}/appcenter/cisco/ndfc/api/v1"
        self.session = requests.Session()
        
    def login(self) -> bool:
        """
        Authenticate with NDFC and obtain access token.
        
        Returns:
            bool: True if login successful
        """
        url = f"https://{self.host}/login"
        payload = {
            "userName": self.username,
            "userPasswd": self.password,
            "domain": "local"
        }
        
        try:
            response = self.session.post(
                url,
                json=payload,
                verify=self.verify_ssl,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            self.token = data.get('token') or data.get('Dcnm-Token')
            
            if self.token:
                self.session.headers.update({
                    'Dcnm-Token': self.token,
                    'Content-Type': 'application/json'
                })
                logger.info(f"Successfully authenticated to NDFC at {self.host}")
                return True
            else:
                logger.error("No token received from NDFC")
                return False
                
        except Exception as e:
            logger.error(f"Failed to authenticate to NDFC: {e}")
            return False
    
    def get_fabrics(self) -> List[Dict[str, Any]]:
        """
        Retrieve all fabrics from NDFC.
        
        Returns:
            List of fabric dictionaries
        """
        url = f"{self.base_url}/lan-fabric/rest/control/fabrics"
        
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            fabrics = response.json()
            logger.info(f"Retrieved {len(fabrics)} fabrics")
            return fabrics
        except Exception as e:
            logger.error(f"Failed to retrieve fabrics: {e}")
            return []
    
    def get_fabric_details(self, fabric_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific fabric.
        
        Args:
            fabric_name: Name of the fabric
            
        Returns:
            Fabric details dictionary
        """
        url = f"{self.base_url}/lan-fabric/rest/control/fabrics/{fabric_name}"
        
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to retrieve fabric details for {fabric_name}: {e}")
            return None
    
    def get_switches(self, fabric_name: str) -> List[Dict[str, Any]]:
        """
        Get all switches in a fabric.
        
        Args:
            fabric_name: Name of the fabric
            
        Returns:
            List of switch dictionaries
        """
        url = f"{self.base_url}/lan-fabric/rest/inventory/allswitches"
        
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            all_switches = response.json()
            
            # Filter switches by fabric
            fabric_switches = [s for s in all_switches if s.get('fabricName') == fabric_name]
            logger.info(f"Retrieved {len(fabric_switches)} switches from fabric {fabric_name}")
            return fabric_switches
        except Exception as e:
            logger.error(f"Failed to retrieve switches for fabric {fabric_name}: {e}")
            return []
    
    def get_networks(self, fabric_name: str) -> List[Dict[str, Any]]:
        """
        Get all networks/VLANs in a fabric.
        
        Args:
            fabric_name: Name of the fabric
            
        Returns:
            List of network dictionaries
        """
        url = f"{self.base_url}/lan-fabric/rest/top-down/fabrics/{fabric_name}/networks"
        
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            networks = response.json()
            logger.info(f"Retrieved {len(networks)} networks from fabric {fabric_name}")
            return networks
        except Exception as e:
            logger.error(f"Failed to retrieve networks for fabric {fabric_name}: {e}")
            return []
    
    def get_vrfs(self, fabric_name: str) -> List[Dict[str, Any]]:
        """
        Get all VRFs in a fabric.
        
        Args:
            fabric_name: Name of the fabric
            
        Returns:
            List of VRF dictionaries
        """
        url = f"{self.base_url}/lan-fabric/rest/top-down/fabrics/{fabric_name}/vrfs"
        
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            vrfs = response.json()
            logger.info(f"Retrieved {len(vrfs)} VRFs from fabric {fabric_name}")
            return vrfs
        except Exception as e:
            logger.error(f"Failed to retrieve VRFs for fabric {fabric_name}: {e}")
            return []
    
    def get_policies(self, fabric_name: str) -> List[Dict[str, Any]]:
        """
        Get policies configured in a fabric.
        
        Args:
            fabric_name: Name of the fabric
            
        Returns:
            List of policy dictionaries
        """
        url = f"{self.base_url}/lan-fabric/rest/control/policies"
        
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            all_policies = response.json()
            
            # Filter policies by fabric if applicable
            fabric_policies = [p for p in all_policies if p.get('fabricName') == fabric_name]
            logger.info(f"Retrieved {len(fabric_policies)} policies from fabric {fabric_name}")
            return fabric_policies
        except Exception as e:
            logger.error(f"Failed to retrieve policies for fabric {fabric_name}: {e}")
            return []
    
    def export_fabric_full(self, fabric_name: str) -> Dict[str, Any]:
        """
        Export complete fabric configuration.
        
        Args:
            fabric_name: Name of the fabric to export
            
        Returns:
            Dictionary containing all fabric data
        """
        logger.info(f"Starting full export of fabric: {fabric_name}")
        
        fabric_data = {
            "fabric_name": fabric_name,
            "fabric_details": self.get_fabric_details(fabric_name),
            "switches": self.get_switches(fabric_name),
            "networks": self.get_networks(fabric_name),
            "vrfs": self.get_vrfs(fabric_name),
            "policies": self.get_policies(fabric_name)
        }
        
        logger.info(f"Completed export of fabric: {fabric_name}")
        return fabric_data
    
    def logout(self):
        """Logout from NDFC."""
        try:
            self.session.close()
            logger.info("Logged out from NDFC")
        except Exception as e:
            logger.error(f"Error during logout: {e}")
