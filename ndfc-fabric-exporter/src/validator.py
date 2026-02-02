"""
YAML Validation Module for NDFC Fabric Exporter.

Validates generated YAML files for correctness and schema compliance.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from jsonschema import validate, ValidationError, Draft7Validator
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


class YAMLValidator:
    """Validate generated YAML configuration files."""
    
    def __init__(self):
        """Initialize validator."""
        self.validation_results = []
    
    def validate_yaml_syntax(self, file_path: str) -> bool:
        """
        Validate YAML file syntax.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            True if syntax is valid
        """
        try:
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            logger.info(f"✓ Valid YAML syntax: {file_path}")
            return True
        except yaml.YAMLError as e:
            logger.error(f"✗ Invalid YAML syntax in {file_path}: {e}")
            return False
    
    def validate_fabric_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate fabric configuration structure.
        
        Args:
            config: Fabric configuration dictionary
            
        Returns:
            True if valid
        """
        required_fields = ['fabric_name', 'fabric_type']
        
        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False
        
        return True
    
    def validate_vrf_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate VRF configuration structure.
        
        Args:
            config: VRF configuration dictionary
            
        Returns:
            True if valid
        """
        required_fields = ['fabric', 'vrf_name']
        
        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False
        
        return True
    
    def validate_network_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate network configuration structure.
        
        Args:
            config: Network configuration dictionary
            
        Returns:
            True if valid
        """
        required_fields = ['fabric', 'net_name', 'vrf_name']
        
        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False
        
        return True
    
    def validate_inventory(self, inventory: Dict[str, Any]) -> bool:
        """
        Validate Ansible inventory structure.
        
        Args:
            inventory: Inventory dictionary
            
        Returns:
            True if valid
        """
        if 'all' not in inventory:
            logger.error("Missing 'all' group in inventory")
            return False
        
        return True
    
    def validate_directory(self, directory: str) -> Dict[str, List[str]]:
        """
        Validate all YAML files in a directory.
        
        Args:
            directory: Directory containing YAML files
            
        Returns:
            Dictionary with validation results
        """
        results = {
            "valid": [],
            "invalid": [],
            "errors": []
        }
        
        yaml_files = Path(directory).glob("*.yml")
        
        for yaml_file in yaml_files:
            if self.validate_yaml_syntax(str(yaml_file)):
                results["valid"].append(str(yaml_file))
            else:
                results["invalid"].append(str(yaml_file))
        
        return results
    
    def display_validation_report(self, results: Dict[str, List[str]]):
        """
        Display validation results in a formatted table.
        
        Args:
            results: Validation results dictionary
        """
        table = Table(title="YAML Validation Report")
        table.add_column("Status", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Files")
        
        # Valid files
        if results["valid"]:
            files_str = "\n".join([Path(f).name for f in results["valid"]])
            table.add_row(
                "[green]✓ Valid[/green]",
                str(len(results["valid"])),
                files_str
            )
        
        # Invalid files
        if results["invalid"]:
            files_str = "\n".join([Path(f).name for f in results["invalid"]])
            table.add_row(
                "[red]✗ Invalid[/red]",
                str(len(results["invalid"])),
                files_str
            )
        
        console.print(table)
        
        # Summary
        total = len(results["valid"]) + len(results["invalid"])
        if total > 0:
            success_rate = (len(results["valid"]) / total) * 100
            console.print(f"\n[bold]Success Rate: {success_rate:.1f}%[/bold]")


def validate_output_directory(output_dir: str):
    """
    Validate all generated YAML files in output directory.
    
    Args:
        output_dir: Directory containing generated files
    """
    console.print(f"[cyan]Validating YAML files in: {output_dir}[/cyan]\n")
    
    validator = YAMLValidator()
    results = validator.validate_directory(output_dir)
    validator.display_validation_report(results)
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        console.print("[red]Usage: python validator.py <output_directory>[/red]")
        sys.exit(1)
    
    output_dir = sys.argv[1]
    validate_output_directory(output_dir)
