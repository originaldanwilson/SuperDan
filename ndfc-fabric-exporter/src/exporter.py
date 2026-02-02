#!/usr/bin/env python3
"""
Main CLI script for NDFC Fabric Exporter.
"""

import click
import logging
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from ndfc_client import NDFCClient
from yaml_generator import AnsibleYAMLGenerator

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)
console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """NDFC Fabric Exporter - Extract and convert NDFC fabrics to Ansible YAML."""
    pass


@cli.command()
@click.option('--host', required=True, help='NDFC controller hostname or IP')
@click.option('--username', required=True, help='NDFC username')
@click.option('--password', required=True, prompt=True, hide_input=True, help='NDFC password')
@click.option('--verify-ssl/--no-verify-ssl', default=False, help='Verify SSL certificates')
def list_fabrics(host, username, password, verify_ssl):
    """List all fabrics available in NDFC."""
    client = NDFCClient(host, username, password, verify_ssl)
    
    if not client.login():
        console.print("[red]Failed to authenticate to NDFC[/red]")
        sys.exit(1)
    
    fabrics = client.get_fabrics()
    
    if not fabrics:
        console.print("[yellow]No fabrics found[/yellow]")
        client.logout()
        return
    
    table = Table(title="NDFC Fabrics")
    table.add_column("Fabric Name", style="cyan")
    table.add_column("Fabric Type", style="magenta")
    table.add_column("Template", style="green")
    table.add_column("ASNI", style="yellow")
    
    for fabric in fabrics:
        table.add_row(
            fabric.get("fabricName", "N/A"),
            fabric.get("fabricType", "N/A"),
            fabric.get("templateName", "N/A"),
            str(fabric.get("asn", "N/A"))
        )
    
    console.print(table)
    client.logout()


@cli.command()
@click.option('--host', required=True, help='NDFC controller hostname or IP')
@click.option('--username', required=True, help='NDFC username')
@click.option('--password', required=True, prompt=True, hide_input=True, help='NDFC password')
@click.option('--fabric', required=True, help='Fabric name to export')
@click.option('--output-dir', default='output', help='Output directory for generated files')
@click.option('--verify-ssl/--no-verify-ssl', default=False, help='Verify SSL certificates')
@click.option('--save-json/--no-save-json', default=True, help='Save raw JSON data')
def export(host, username, password, fabric, output_dir, verify_ssl, save_json):
    """Export fabric configuration and generate Ansible YAML files."""
    console.print(f"[bold cyan]Exporting fabric: {fabric}[/bold cyan]")
    
    # Initialize NDFC client
    client = NDFCClient(host, username, password, verify_ssl)
    
    if not client.login():
        console.print("[red]Failed to authenticate to NDFC[/red]")
        sys.exit(1)
    
    # Export fabric data
    console.print("[yellow]Extracting fabric data from NDFC...[/yellow]")
    fabric_data = client.export_fabric_full(fabric)
    
    # Save raw JSON if requested
    if save_json:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        json_file = output_path / f"fabric_data_{fabric}.json"
        
        with open(json_file, 'w') as f:
            json.dump(fabric_data, f, indent=2)
        
        console.print(f"[green]Saved raw data to: {json_file}[/green]")
    
    # Generate Ansible YAML files
    console.print("[yellow]Generating Ansible YAML files...[/yellow]")
    generator = AnsibleYAMLGenerator(output_dir)
    generated_files = generator.generate_all(fabric_data)
    
    # Display generated files
    table = Table(title="Generated Files")
    table.add_column("Type", style="cyan")
    table.add_column("File Path", style="green")
    
    for config_type, file_path in generated_files.items():
        table.add_row(config_type.replace('_', ' ').title(), file_path)
    
    console.print(table)
    console.print(f"\n[bold green]✓ Export completed successfully![/bold green]")
    console.print(f"[cyan]Files saved to: {output_dir}[/cyan]")
    
    client.logout()


@cli.command()
@click.option('--config-file', type=click.Path(exists=True), required=True, help='Configuration file with NDFC details')
@click.option('--fabric', required=True, help='Fabric name to export')
@click.option('--output-dir', default='output', help='Output directory for generated files')
def export_from_config(config_file, fabric, output_dir):
    """Export fabric using configuration from a JSON/YAML file."""
    config_path = Path(config_file)
    
    if config_path.suffix == '.json':
        with open(config_path) as f:
            config = json.load(f)
    else:
        console.print("[red]Only JSON config files are currently supported[/red]")
        sys.exit(1)
    
    # Extract config parameters
    host = config.get('ndfc_host')
    username = config.get('ndfc_username')
    password = config.get('ndfc_password')
    verify_ssl = config.get('verify_ssl', False)
    
    if not all([host, username, password]):
        console.print("[red]Configuration file must contain: ndfc_host, ndfc_username, ndfc_password[/red]")
        sys.exit(1)
    
    # Use the export function
    ctx = click.get_current_context()
    ctx.invoke(export, 
               host=host, 
               username=username, 
               password=password, 
               fabric=fabric, 
               output_dir=output_dir, 
               verify_ssl=verify_ssl,
               save_json=True)


if __name__ == '__main__':
    cli()
