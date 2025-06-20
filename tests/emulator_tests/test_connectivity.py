# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility script to test connectivity to Azure Functions host.

This script can be run to check if the Azure Functions host is accessible
and responsive, which can help diagnose connection refused errors.
"""

import argparse
import logging
import os
import requests
import sys
import shutil
import subprocess
import time


def check_host_health(url, max_retries=30, retry_delay=1, check_process=True):
    """Test connectivity to an Azure Functions host.
    
    Args:
        url: The URL of the Azure Functions host to check
        max_retries: Maximum number of health check attempts
        retry_delay: Delay in seconds between health check attempts
        check_process: Whether to check if Core Tools is running
        
    Returns:
        True if host is healthy, False otherwise
    """
    logging.info(f"Testing connectivity to Azure Functions host at {url}")
    
    # Check if Core Tools process is running
    if check_process:
        try:
            # Check for running Core Tools process
            import psutil
            func_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.cmdline()
                    if cmdline and any('func' in cmd.lower() for cmd in cmdline) and any('host' in cmd.lower() for cmd in cmdline):
                        func_processes.append((proc.pid, cmdline))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                    
            if func_processes:
                logging.info(f"Found {len(func_processes)} running Azure Functions Core Tools processes:")
                for pid, cmdline in func_processes:
                    logging.info(f"  PID {pid}: {' '.join(cmdline)}")
            else:
                logging.warning("No running Azure Functions Core Tools processes found!")
        except ImportError:
            logging.warning("psutil package not available. Cannot check for running Core Tools processes.")
    
    # Try to connect to the host
    for i in range(max_retries):
        try:
            r = requests.get(url, timeout=5)
            if 200 <= r.status_code < 300:
                logging.info(f"✅ Host is healthy! Status code: {r.status_code}")
                logging.info(f"Response headers: {r.headers}")
                return True
            else:
                logging.warning(f"Attempt {i+1}/{max_retries}: Host returned status code {r.status_code}")
                logging.debug(f"Response content: {r.text[:500]}")
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Attempt {i+1}/{max_retries}: Connection error: {e}")
        except requests.exceptions.Timeout:
            logging.warning(f"Attempt {i+1}/{max_retries}: Request timed out after 5 seconds")
        except Exception as e:
            logging.warning(f"Attempt {i+1}/{max_retries}: Unexpected error: {e}")
            
        if i < max_retries - 1:
            time.sleep(retry_delay)
    
    # Check for common issues
    logging.error(f"❌ Host is not responding after {max_retries} attempts")
    try:
        # Check if the port is in use by another process
        import socket
        host_port = int(url.split(':')[-1].split('/')[0])
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', host_port))
        if result == 0:
            logging.error(f"Port {host_port} is open, but the host is not responding correctly.")
            logging.error("Another process might be using this port or the Functions host is not responding properly.")
        else:
            logging.error(f"Port {host_port} is not open. Azure Functions host is not listening on this port.")
        s.close()
    except Exception as e:
        logging.error(f"Error checking port: {e}")
    
    return False


def check_function_endpoint(url, function_name, max_retries=3, retry_delay=1):
    """Test connectivity to a specific function endpoint.
    
    Args:
        url: The base URL of the Azure Functions host
        function_name: The name of the function to check
        max_retries: Maximum number of health check attempts
        retry_delay: Delay in seconds between health check attempts
        
    Returns:
        True if function endpoint is accessible, False otherwise
    """
    function_url = f"{url.rstrip('/')}/api/{function_name}?code=testFunctionKey"
    logging.info(f"Testing connectivity to function endpoint at {function_url}")
    
    for i in range(max_retries):
        try:
            r = requests.get(function_url, timeout=5)
            logging.info(f"✅ Function endpoint is accessible! Status code: {r.status_code}")
            logging.info(f"Response: {r.text[:100]}...")
            return True
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Attempt {i+1}/{max_retries}: Connection error: {e}")
        except requests.exceptions.Timeout:
            logging.warning(f"Attempt {i+1}/{max_retries}: Request timed out after 5 seconds")
        except Exception as e:
            logging.warning(f"Attempt {i+1}/{max_retries}: Unexpected error: {e}")
            
        if i < max_retries - 1:
            time.sleep(retry_delay)
    
    logging.error(f"❌ Function endpoint is not responding after {max_retries} attempts")
    return False


def main():
    """Run the connectivity test."""
    parser = argparse.ArgumentParser(description='Test connectivity to Azure Functions host')
    parser.add_argument('--url', default='http://localhost:7071', 
                        help='URL of the Azure Functions host')
    parser.add_argument('--function', 
                        help='Name of a function to test (optional)')
    parser.add_argument('--max-retries', type=int, default=30,
                        help='Maximum number of health check attempts')
    parser.add_argument('--retry-delay', type=int, default=1,
                        help='Delay in seconds between health check attempts')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--check-process', action='store_true',
                        help='Check if Azure Functions Core Tools process is running')
    parser.add_argument('--debug-info', action='store_true',
                        help='Print debug info about the system and environment')
    
    args = parser.parse_args()
    
    # Configure logging
    logging_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Print system info if requested
    if args.debug_info:
        print_debug_info()
    
    # Test host health
    host_healthy = check_host_health(
        args.url, 
        max_retries=args.max_retries, 
        retry_delay=args.retry_delay,
        check_process=args.check_process
    )
    
    # Test function endpoint if requested and host is healthy
    if host_healthy and args.function:
        function_healthy = check_function_endpoint(
            args.url, 
            args.function, 
            max_retries=3, 
            retry_delay=1
        )
        if not function_healthy:
            sys.exit(1)
    
    if not host_healthy:
        # Print suggestions for troubleshooting
        logging.error("\nTroubleshooting suggestions:")
        logging.error("1. Check if Azure Functions Core Tools is installed correctly")
        logging.error("2. Check if the host process has started (use --check-process flag)")
        logging.error("3. Check if the port is already in use by another process")
        logging.error("4. Check host.json and local.settings.json for configuration issues")
        logging.error("5. Try running Azure Functions Core Tools manually to see detailed errors")
        logging.error("6. Set PYAZURE_WEBHOST_DEBUG=true to see more detailed output in tests")
        sys.exit(1)
    
    sys.exit(0)


def print_debug_info():
    """Print debug information about the system and environment."""
    logging.info("=== System Information ===")
    
    # OS information
    import platform
    logging.info(f"Operating System: {platform.platform()}")
    logging.info(f"Python Version: {platform.python_version()}")
    
    # Environment variables related to Azure Functions
    logging.info("\n=== Environment Variables ===")
    for key, value in sorted(os.environ.items()):
        if any(azure_key in key.lower() for azure_key in ['azure', 'function', 'webhost', 'python']):
            # Mask sensitive information
            if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'password', 'token']):
                logging.info(f"{key}=***MASKED***")
            else:
                logging.info(f"{key}={value}")
    
    # Check for Azure Functions Core Tools
    logging.info("\n=== Azure Functions Core Tools ===")
    core_tools_paths = [
        os.environ.get('CORE_TOOLS_EXE_PATH'),
        shutil.which('func'),
        shutil.which('func.exe'),
    ]
    
    found = False
    for path in core_tools_paths:
        if path and os.path.exists(path):
            logging.info(f"Found Core Tools at: {path}")
            found = True
            
            # Try to get version
            try:
                result = subprocess.run([path, '--version'], 
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logging.info(f"Core Tools Version: {result.stdout.strip()}")
                else:
                    logging.warning(f"Failed to get Core Tools version: {result.stderr.strip()}")
            except Exception as e:
                logging.warning(f"Error checking Core Tools version: {e}")
    
    if not found:
        logging.warning("Azure Functions Core Tools not found in PATH or environment variables")


if __name__ == "__main__":
    main()
