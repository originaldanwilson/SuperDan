#!/usr/bin/env python3
"""
Output Formatter for Network Device Check Scripts

This module provides utilities to format command output from network devices
in a readable format suitable for documentation and change management records.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any
import textwrap


def create_output_directory(base_dir: str, check_type: str) -> str:
    """
    Create output directory with timestamp.
    
    Args:
        base_dir: Base directory name
        check_type: Type of check ('precheck' or 'postcheck')
    
    Returns:
        str: Full path to created directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(base_dir, f"{check_type}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
    
    Returns:
        str: Sanitized filename safe for filesystem
    """
    # Replace spaces and special characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def format_command_output(device: str, command: str, output: str, 
                         execution_time: float, status: str) -> str:
    """
    Format command output for documentation.
    
    Args:
        device: Device hostname/IP
        command: Command that was executed
        output: Raw command output
        execution_time: Time taken to execute command
        status: Command execution status
    
    Returns:
        str: Formatted output string
    """
    separator = "=" * 80
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    formatted_output = f"""
{separator}
DEVICE: {device}
COMMAND: {command}
TIMESTAMP: {timestamp}
EXECUTION TIME: {execution_time:.2f} seconds
STATUS: {status}
{separator}

{output}

{separator}

"""
    return formatted_output


def save_device_output(output_dir: str, device: str, command: str, 
                      output: str, execution_time: float, status: str) -> str:
    """
    Save individual command output to a file.
    
    Args:
        output_dir: Output directory path
        device: Device hostname/IP
        command: Command that was executed
        output: Raw command output
        execution_time: Time taken to execute command
        status: Command execution status
    
    Returns:
        str: Path to saved file
    """
    # Create filename from device and command
    safe_command = sanitize_filename(command.replace(" ", "_"))
    safe_device = sanitize_filename(device)
    filename = f"{safe_device}_{safe_command}.txt"
    filepath = os.path.join(output_dir, filename)
    
    formatted_content = format_command_output(device, command, output, 
                                            execution_time, status)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(formatted_content)
    
    return filepath


def create_summary_report(output_dir: str, check_type: str, results: Dict[str, Dict]) -> str:
    """
    Create a comprehensive summary report of all devices and commands.
    
    Args:
        output_dir: Output directory path
        check_type: Type of check ('precheck' or 'postcheck')
        results: Dictionary containing all device results
    
    Returns:
        str: Path to summary report file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_filename = f"{check_type}_summary_report.txt"
    summary_filepath = os.path.join(output_dir, summary_filename)
    
    total_devices = len(results)
    successful_devices = sum(1 for device_data in results.values() 
                           if device_data.get('connection_status') == 'SUCCESS')
    failed_devices = total_devices - successful_devices
    
    with open(summary_filepath, 'w', encoding='utf-8') as f:
        # Header
        f.write("=" * 80 + "\n")
        f.write(f"NETWORK DEVICE {check_type.upper()} SUMMARY REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"Total Devices: {total_devices}\n")
        f.write(f"Successful Connections: {successful_devices}\n")
        f.write(f"Failed Connections: {failed_devices}\n")
        f.write("=" * 80 + "\n\n")
        
        # Device Status Overview
        f.write("DEVICE CONNECTION STATUS:\n")
        f.write("-" * 40 + "\n")
        for device, device_data in results.items():
            status = device_data.get('connection_status', 'UNKNOWN')
            connection_time = device_data.get('connection_time', 0)
            f.write(f"{device:<25} {status:<10} ({connection_time:.2f}s)\n")
            
            # Show connection error if failed
            if status == 'FAILED' and 'connection_error' in device_data:
                error_msg = device_data['connection_error']
                wrapped_error = textwrap.fill(f"  Error: {error_msg}", 
                                           width=70, subsequent_indent="    ")
                f.write(f"{wrapped_error}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        
        # Command Execution Summary
        f.write("COMMAND EXECUTION SUMMARY:\n")
        f.write("-" * 40 + "\n")
        
        for device, device_data in results.items():
            if device_data.get('connection_status') == 'SUCCESS':
                f.write(f"\nDevice: {device}\n")
                f.write("-" * len(f"Device: {device}") + "\n")
                
                commands = device_data.get('commands', {})
                for command, cmd_data in commands.items():
                    status = cmd_data.get('status', 'UNKNOWN')
                    exec_time = cmd_data.get('execution_time', 0)
                    output_lines = len(cmd_data.get('output', '').split('\n'))
                    
                    f.write(f"  {command:<35} {status:<10} "
                           f"({exec_time:.2f}s, {output_lines} lines)\n")
                    
                    # Show command error if failed
                    if status == 'FAILED' and 'error' in cmd_data:
                        error_msg = cmd_data['error']
                        wrapped_error = textwrap.fill(f"    Error: {error_msg}", 
                                                   width=70, subsequent_indent="      ")
                        f.write(f"{wrapped_error}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("END OF SUMMARY REPORT\n")
        f.write("=" * 80 + "\n")
    
    return summary_filepath


def save_results_json(output_dir: str, check_type: str, results: Dict[str, Dict]) -> str:
    """
    Save results in JSON format for programmatic processing.
    
    Args:
        output_dir: Output directory path
        check_type: Type of check ('precheck' or 'postcheck')
        results: Dictionary containing all device results
    
    Returns:
        str: Path to JSON results file
    """
    json_filename = f"{check_type}_results.json"
    json_filepath = os.path.join(output_dir, json_filename)
    
    # Add metadata
    results_with_metadata = {
        'metadata': {
            'check_type': check_type,
            'timestamp': datetime.now().isoformat(),
            'total_devices': len(results),
            'successful_devices': sum(1 for device_data in results.values() 
                                   if device_data.get('connection_status') == 'SUCCESS')
        },
        'results': results
    }
    
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(results_with_metadata, f, indent=2, ensure_ascii=False)
    
    return json_filepath


if __name__ == "__main__":
    # Test the formatter functions
    print("Output formatter utilities loaded successfully")
    print("Available functions:")
    print("- create_output_directory()")
    print("- format_command_output()")
    print("- save_device_output()")
    print("- create_summary_report()")
    print("- save_results_json()")
