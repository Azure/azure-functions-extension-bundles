# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Simplified unittest helpers for Azure Functions extension bundles tests.

This version only supports running tests via Azure Functions Core Tools,
removing dependencies on azure_functions_worker and proxy_worker modules.
"""

import configparser
import json
import logging
import os
import pathlib
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

# Constants
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
TESTS_ROOT = PROJECT_ROOT / 'tests'
EMULATOR_TESTS_FOLDER = pathlib.Path('emulator_tests')
BUILD_DIR = TESTS_ROOT / 'build'  # Same as BUILD_DIR in test_setup.py - webhost extracted here
WORKER_CONFIG = PROJECT_ROOT / 'worker.config.ini'
PYAZURE_WEBHOST_DEBUG = 'PYAZURE_WEBHOST_DEBUG'
ARCHIVE_WEBHOST_LOGS = 'ARCHIVE_WEBHOST_LOGS'
ON_WINDOWS = platform.system() == 'Windows'
LOCALHOST = "127.0.0.1"
DEFAULT_FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI = 'http://localhost:3000'
# This definition is safe by design, but it might trigger the CI security checks. If that happens, let’s change it so it’s created and applied dynamically.
DEFAULT_MYSQL_CONNECTION_STRING = "Server=localhost;UserID=root;Password=password;Database=testdb;Port=3307"
MYSQL_WEBSITE_SITE_NAME = "SampleMysqlPythonApp"
DEFAULT_PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'

def _get_bundle_config():
    """Get the bundle configuration from bundleConfig.json."""
    bundle_config_path = PROJECT_ROOT / 'src' / 'Microsoft.Azure.Functions.ExtensionBundle' / 'bundleConfig.json'
    
    # Debug: Print the path being checked
    if is_envvar_true(PYAZURE_WEBHOST_DEBUG):
        print(f"[DEBUG] Looking for bundleConfig.json at: {bundle_config_path}")
        print(f"[DEBUG] Path exists: {bundle_config_path.exists()}")
        
    try:
        with open(bundle_config_path, 'r') as f:
            config = json.load(f)
            
            # Debug: Print the loaded config
            if is_envvar_true(PYAZURE_WEBHOST_DEBUG):
                print(f"[DEBUG] Loaded bundle config: {config}")
                
            return config
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        # Debug: Print why we're falling back
        if is_envvar_true(PYAZURE_WEBHOST_DEBUG):
            print(f"[DEBUG] Failed to load bundleConfig.json: {e}")
            print(f"[DEBUG] Using fallback configuration")
            
        # Fallback to default configuration if file is not found or invalid
        return {
            'bundleId': 'Microsoft.Azure.Functions.ExtensionBundle',
            'bundleVersion': '4.25.0',
            'isPreviewBundle': False
        }


def _get_bundle_version():
    """Get the bundle version from bundleConfig.json."""
    config = _get_bundle_config()
    return config.get('bundleVersion', '4.25.0')


def _get_bundle_id():
    """Get the bundle ID from bundleConfig.json."""
    config = _get_bundle_config()
    return config.get('bundleId', 'Microsoft.Azure.Functions.ExtensionBundle')


def _get_host_json_template():
    """Get the host.json template with the correct bundle ID and version."""
    bundle_version = _get_bundle_version()
    bundle_id = _get_bundle_id()
    
    return f"""\
{{
    "version": "2.0",
    "logging": {{"logLevel": {{"default": "Trace"}}}},
    "extensionBundle": {{
    "id": "{bundle_id}",
    "version": "{bundle_version}"
    }}
}}
"""

# The template of host.json for test functions - generated dynamically
def get_host_json_template():
    """Get the current host.json template with the correct bundle configuration."""
    return _get_host_json_template()


def is_envvar_true(name):
    """Check if an environment variable is set to a 'truthy' value."""
    value = os.environ.get(name, '').strip().lower()
    return value in ('1', 'true', 'yes', 'y')


class WebHostTestCase(unittest.TestCase):
    """Base class for integration tests that need a WebHost.

    Simplified test case that automatically starts up a WebHost instance
    and logs errors if the host fails to start.
    """
    host_stdout_logger = logging.getLogger('webhosttests')

    @classmethod
    def get_script_dir(cls):
        """Return the directory containing the function app for testing.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        """Set up the test environment before running any tests."""
        script_dir = pathlib.Path(cls.get_script_dir())

        # Only capture output to file if debug mode is disabled
        cls.host_stdout = None if is_envvar_true(PYAZURE_WEBHOST_DEBUG) \
            else tempfile.NamedTemporaryFile('w+t')

        try:
            _setup_func_app(TESTS_ROOT / script_dir)
            cls.webhost = start_webhost(script_dir=script_dir, stdout=cls.host_stdout)
            
            if not cls.webhost.is_healthy():
                error_message = 'WebHost failed to start or is not responding.'
                if cls.host_stdout is not None:
                    cls.host_stdout.seek(0)
                    host_output = cls.host_stdout.read()
                    if host_output:
                        cls.host_stdout_logger.error(f'{error_message}\n{cls.host_stdout.name}: {host_output}')
                raise RuntimeError(error_message)
        except Exception as ex:
            cls.host_stdout_logger.error(f"Failed to start WebHost: {ex}")
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are run."""
        # Clean up webhost
        if hasattr(cls, 'webhost') and cls.webhost:
            try:
                cls.webhost.close()
            except Exception as e:
                cls.host_stdout_logger.warning(f"Error closing webhost: {e}")
            cls.webhost = None

        # Handle output logging and archival
        if hasattr(cls, 'host_stdout') and cls.host_stdout is not None:
            try:
                if is_envvar_true(ARCHIVE_WEBHOST_LOGS):
                    cls.host_stdout.seek(0)
                    content = cls.host_stdout.read()
                    if content and len(content) > 0:
                        version_info = sys.version_info
                        log_file = (
                            "logs/"
                            f"{cls.__module__}_{cls.__name__}"
                            f"{version_info.minor}_webhost.log"
                        )
                        os.makedirs(os.path.dirname(log_file), exist_ok=True)
                        with open(log_file, 'w+') as file:
                            file.write(content)
                        cls.host_stdout_logger.info(f"WebHost log archived to {log_file}")
                
                cls.host_stdout.close()
            except Exception as e:
                cls.host_stdout_logger.warning(f"Error handling host stdout: {e}")
            finally:
                cls.host_stdout = None

        # Clean up function app
        try:
            script_dir = pathlib.Path(cls.get_script_dir())
            _teardown_func_app(TESTS_ROOT / script_dir)
        except Exception as e:
            cls.host_stdout_logger.warning(f"Error cleaning up function app: {e}")


def _find_open_port():
    """Find an available port to use for the Azure Functions host."""
    with socket.socket() as s:
        s.bind((LOCALHOST, 0))
        s.listen(1)
        return s.getsockname()[1]


def popen_webhost(*, stdout, stderr, script_root, port=None):
    """Start the Azure Functions host process."""    
    testconfig = None
    if WORKER_CONFIG.exists():
        testconfig = configparser.ConfigParser()
        testconfig.read(WORKER_CONFIG)    # Get Core Tools executable path
    coretools_exe = os.environ.get('CORE_TOOLS_EXE_PATH')
    if not coretools_exe:
        # Check for HOST_VERSION to use version-specific directory
        host_version = os.environ.get('HOST_VERSION')
        
        # Default to the webhost directory structure from test_setup.py
        # BUILD_DIR / "webhost" or BUILD_DIR / "webhost-{version}" is where test_setup.py extracts Core Tools
        if host_version:
            webhost_subdir = f"webhost-{host_version}"
        else:
            webhost_subdir = "webhost"
        
        if ON_WINDOWS:
            default_path = BUILD_DIR / webhost_subdir / "func.exe"
        else:
            default_path = BUILD_DIR / webhost_subdir / "func"
        
        if default_path.exists():
            coretools_exe = str(default_path)
        else:
            # Try to find Core Tools in the build directory
            potential_paths = [
                BUILD_DIR / webhost_subdir / "func.exe",
                BUILD_DIR / webhost_subdir / "func"
            ]
            for path in potential_paths:
                if path.exists():
                    coretools_exe = str(path)
                    break
    
    if not coretools_exe:
        raise RuntimeError('\n'.join([
            'Unable to locate Azure Functions Core Tools binary.',
            'Please do one of the following:',
            ' * run the following command from the root folder of',
            '   the project:',
            '',
            f'cd tests && python -m invoke -c test_setup webhost',
            '',
            ' * or set the CORE_TOOLS_EXE_PATH environment variable',
            '   to point to the func.exe or func binary.',
            '',
            'Setting "export PYAZURE_WEBHOST_DEBUG=true" to get the full',
            'stdout and stderr from function host.'
        ]))

    coretools_exe = coretools_exe.strip()
    
    # Log the selected version for debugging
    host_version = os.environ.get('HOST_VERSION', 'default')
    logging.info(f"HOST_VERSION: {host_version}")
    logging.info(f"Using Azure Functions Core Tools at: {coretools_exe}")
    
    # Check if the Core Tools binary exists and is executable
    if not os.path.isfile(coretools_exe):
        raise RuntimeError(f"Core Tools binary not found at {coretools_exe}")
    
    if not ON_WINDOWS and not os.access(coretools_exe, os.X_OK):
        logging.warning(f"Core Tools binary at {coretools_exe} is not executable. Attempting to fix permissions.")
        try:
            os.chmod(coretools_exe, os.stat(coretools_exe).st_mode | 0o111)
        except Exception as e:
            logging.error(f"Failed to set executable permissions: {e}")
    
    hostexe_args = [str(coretools_exe), 'host', 'start', '--verbose']
    if port is not None:
        hostexe_args.extend(['--port', str(port)])    
        logging.info(f"Starting Core Tools with command: {' '.join(hostexe_args)}")
    logging.info(f"Working directory: {script_root}")

    # Check if the directory exists
    if not os.path.isdir(script_root):
        raise RuntimeError(f"Function app directory does not exist: {script_root}")    # Set up the environment for the host
    extra_env = {
        'AzureWebJobsScriptRoot': str(script_root),
        'host:logger:consoleLoggingMode': 'always',
        'AZURE_FUNCTIONS_ENVIRONMENT': 'development',
        'AzureWebJobsSecretStorageType': 'files',
        'FUNCTIONS_WORKER_RUNTIME': 'python',
        'FUNCTIONS_WORKER_RUNTIME_VERSION': f'{sys.version_info.major}.{sys.version_info.minor}',  # Use current Python version
        'AzureWebJobsStorage': os.environ.get('AzureWebJobsStorage', 'UseDevelopmentStorage=true'),
        'FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI': os.environ.get('FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI', DEFAULT_FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI),
        "MySqlConnectionString": os.environ.get('MySqlConnectionString', DEFAULT_MYSQL_CONNECTION_STRING),
        "PYTHON_ISOLATE_WORKER_DEPENDENCIES": os.environ.get('PYTHON_ISOLATE_WORKER_DEPENDENCIES', DEFAULT_PYTHON_ISOLATE_WORKER_DEPENDENCIES),
        "WEBSITE_SITE_NAME": MYSQL_WEBSITE_SITE_NAME,
        "PYTHON_ENABLE_WORKER_EXTENSIONS": '1'
    }  # Add connection strings from config
    if testconfig and 'azure' in testconfig:
        for key in ['storage_key', 'cosmosdb_key', 'eventhub_key', 
                   'servicebus_key', 'sql_key', 'eventgrid_topic_uri', 
                   'eventgrid_topic_key']:
            value = testconfig['azure'].get(key)
            if value:
                # Convert key name to the appropriate connection string format
                env_key = f"AzureWebJobs{key.split('_')[0].capitalize()}"
                if 'key' in key:
                    env_key += "ConnectionString"
                elif 'uri' in key:
                    env_key += "Uri"
                extra_env[env_key] = value    # Log the environment setup
    logging.debug(f"Function host environment: {extra_env}")    # Write manual execution instructions to a file
    config_file = pathlib.Path(script_root) / "webhost_config.txt"
    with open(config_file, 'w') as f:
        f.write("-" * 70 + "\n")
        f.write("To run this command manually, execute the following:\n\n")
        f.write("Environment Variables:\n\n")
        
        # Create PowerShell formatted environment variables
        for key, value in extra_env.items():
            if ON_WINDOWS:
                f.write(f"$env:{key} = '{value}'\n")
            else:
                f.write(f"export {key}='{value}'\n")
        
        f.write("\nCurrent Directory:\n\n")
        f.write(f"cd {script_root}\n")
        
        f.write("\nRun core tools:\n\n")
        f.write(f"{coretools_exe} {' '.join(hostexe_args[1:])}\n")  # Skip the executable name
          # Add host.json content
        f.write("\n" + "-" * 70 + "\n")
        f.write("host.json Configuration:\n\n")
        try:
            host_json_path = pathlib.Path(script_root) / "host.json"
            if host_json_path.exists():
                with open(host_json_path, 'r') as host_file:
                    host_content = host_file.read()
                f.write(host_content)
            else:
                f.write("host.json file not found in the function app directory.\n")
                f.write("Expected template content:\n")
                f.write(get_host_json_template())
        except Exception as e:
            f.write(f"Error reading host.json: {e}\n")
            f.write("Expected template content:\n")
            f.write(get_host_json_template())
        
        f.write("\n" + "-" * 70 + "\n")

    # Also print to console that the config file was created
    print(f"\nWebHost configuration written to: {config_file}")
    print("You can view this file to see how to run the Function Host manually.\n")

    # Start the process
    try:
        return subprocess.Popen(
            hostexe_args,
            cwd=script_root,
            env={
                **os.environ,
                **extra_env,
            },
            stdout=stdout,
            stderr=stderr)
    except Exception as e:
        raise RuntimeError(f"Failed to start Azure Functions Core Tools: {e}")


class _WebHostProxy:
    """Proxy class for interacting with the Functions host."""

    def __init__(self, proc, addr):
        self._proc = proc
        self._addr = addr    
        
    def is_healthy(self):
        """Check if the Function host is responding."""
        import requests  # Import here to avoid global import issues
        try:
            r = requests.get(self._addr, timeout=5)
            if 200 <= r.status_code < 300:
                return True
            else:
                logging.debug(f"Health check returned status code {r.status_code}")
                return False
        except requests.exceptions.ConnectionError as e:
            logging.debug(f"Health check connection error: {e}")
            return False
        except requests.exceptions.Timeout:
            logging.debug("Health check timed out after 5 seconds")
            return False
        except Exception as e:
            logging.debug(f"Unexpected error in health check: {e}")
            return False

    def request(self, meth, funcname, *args, max_retries=0, retry_delay=1, expected_status=None, **kwargs):
        """Make a request to a function in the host with optional retry functionality.
        
        Args:
            meth: HTTP method ('GET', 'POST', etc.)
            funcname: Function name to call
            *args: Positional arguments passed to requests method
            max_retries: Maximum number of retries (default: 0 for original behavior)
            retry_delay: Delay between retries in seconds (default: 1)
            expected_status: Expected status code for success (default: None for any 2xx)
            **kwargs: Keyword arguments passed to requests method
            
        Returns:
            requests.Response: Response object
            
        Raises:
            requests.exceptions.RequestException: If retries are enabled and all attempts fail
        """
        import requests  # Import here to avoid global import issues
        request_method = getattr(requests, meth.lower())
        params = dict(kwargs.pop('params', {}))
        no_prefix = kwargs.pop('no_prefix', False)
        
        # Remove retry parameters from kwargs to avoid passing them to requests
        max_retries = kwargs.pop('max_retries', max_retries)
        retry_delay = kwargs.pop('retry_delay', retry_delay) 
        expected_status = kwargs.pop('expected_status', expected_status)
        
        if 'code' not in params:
            params['code'] = 'testFunctionKey'

        url = self._addr + ('/' if no_prefix else '/api/') + funcname
        
        # If no retries requested, use original behavior
        if max_retries <= 0:
            return request_method(url, *args, params=params, **kwargs)
        
        # Retry logic with detailed logging
        last_response = None
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logging.info(f"Making {meth.upper()} request to {funcname} (attempt {attempt + 1}/{max_retries + 1})")
                response = request_method(url, *args, params=params, **kwargs)
                
                # Handle None response (shouldn't happen with requests, but safety check)
                if response is None:
                    last_error = f"Response is None for {meth.upper()} {funcname}"
                    logging.warning(f"Attempt {attempt + 1}: {last_error}")
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        continue
                    else:
                        break
                
                last_response = response
                
                # Log response details
                logging.info(f"Response status: {response.status_code}")
                logging.info(f"Response headers: {dict(response.headers)}")
                logging.info(f"Response text (first 500 chars): {response.text[:500]}")
                
                # Success condition
                if expected_status is not None:
                    # Check for specific status code
                    if response.status_code == expected_status:
                        logging.info(f"Request successful on attempt {attempt + 1}")
                        return response
                    last_error = f"Unexpected status code {response.status_code} for {meth.upper()} {funcname}. Expected: {expected_status}. Response: {response.text[:500]}"
                else:
                    # Check for any 2xx status code
                    if 200 <= response.status_code < 300:
                        logging.info(f"Request successful on attempt {attempt + 1}")
                        return response
                    last_error = f"Unexpected status code {response.status_code} for {meth.upper()} {funcname}. Response: {response.text[:500]}"
                
                logging.warning(f"Attempt {attempt + 1}: {last_error}")
                
            except Exception as e:
                last_error = f"Exception during {meth.upper()} {funcname}: {str(e)}"
                logging.warning(f"Attempt {attempt + 1}: {last_error}")
            
            # Wait before retry (except on last attempt)
            if attempt < max_retries:
                logging.info(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
        
        # All retries failed - raise exception
        error_msg = f"Request failed after {max_retries + 1} attempts. Last error: {last_error}"
        if last_response is not None:
            error_msg += f"\nLast response status: {last_response.status_code}"
            error_msg += f"\nLast response text: {last_response.text}"
        
        logging.error(error_msg)
        raise requests.exceptions.RequestException(error_msg)

    def request_with_retry(self, meth, funcname, *args, max_retries=3, retry_delay=1, expected_status=200, **kwargs):
        """Convenience method for making requests with retry."""
        return self.request(meth, funcname, *args, 
                           max_retries=max_retries, 
                           retry_delay=retry_delay, 
                           expected_status=expected_status, 
                           **kwargs)

    def wait_and_request(self, meth, funcname, *args, wait_time=5, max_retries=3, retry_delay=1, expected_status=200, **kwargs):
        """Wait for a period then make request with retry (for trigger waiting)."""
        logging.info(f"Waiting {wait_time} seconds for trigger to execute...")
        time.sleep(wait_time)
        
        return self.request(meth, funcname, *args,
                           max_retries=max_retries,
                           retry_delay=retry_delay, 
                           expected_status=expected_status,
                           **kwargs)

    def close(self):
        """Terminate the Function host process."""
        if self._proc.stdout:
            self._proc.stdout.close()
        if self._proc.stderr:
            self._proc.stderr.close()

        self._proc.terminate()
        try:
            self._proc.wait(20)
        except subprocess.TimeoutExpired:
            self._proc.kill()


def start_webhost(*, script_dir=None, stdout=None):
    """Start the Azure Functions host and return a proxy to interact with it."""
    script_root = TESTS_ROOT / script_dir
    
    # Use a temporary file to capture output if not specified
    # This allows us to both log the output and retrieve it in case of failure
    capture_output_for_logging = False
    if stdout is None:
        if is_envvar_true(PYAZURE_WEBHOST_DEBUG):
            stdout = sys.stdout
            logging.info("Capturing Azure Functions host output to stdout")
        else:
            capture_output_for_logging = True
            stdout = tempfile.NamedTemporaryFile('w+', suffix='.log', delete=False)
            logging.info(f"Capturing Azure Functions host output to {stdout.name}")

    port = _find_open_port()

    proc = popen_webhost(stdout=stdout, stderr=subprocess.STDOUT,
                        script_root=script_root, port=port)
    
    addr = f'http://{LOCALHOST}:{port}'
    proxy = _WebHostProxy(proc, addr)
    
    # Implement health check retries instead of fixed sleep
    max_retries = 30
    retry_delay = 1
    logging.info(f"Waiting for Azure Functions host to start on {addr}...")
    
    for i in range(max_retries):
        if proxy.is_healthy():
            logging.info(f"Azure Functions host is healthy after {i+1} attempts")
            return proxy
        
        # If not healthy yet, sleep and retry
        logging.info(f"Waiting for Azure Functions host to start (attempt {i+1}/{max_retries})")
        time.sleep(retry_delay)
    
    # If we get here, we've exhausted all retries
    # Let's check if there was any output from the process
    output = ""
    if capture_output_for_logging and hasattr(stdout, 'name'):
        try:
            if hasattr(stdout, 'close'):
                stdout.close()
            with open(stdout.name, 'r') as f:
                output = f.read()
            # Keep the log file for inspection
            logging.error(f"Azure Functions host output log is available at: {stdout.name}")
        except Exception as e:
            logging.error(f"Failed to read Azure Functions host output: {e}")
    
    error_msg = (
        f"Azure Functions host failed to start after {max_retries} attempts. "
        f"Check logs for errors and ensure the port {port} is available.\n"
    )
    
    if output:
        error_msg += f"\nHost process output:\n{output[:2000]}"
        if len(output) > 2000:
            error_msg += "\n... (output truncated) ..."
    
    raise RuntimeError(error_msg)


def remove_path(path):
    """Remove a file or directory."""
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()


def _setup_func_app(app_root):
    """Set up the function app for testing."""
    host_json = app_root / 'host.json'
    # Create host.json if it doesn't exist
    if not host_json.exists():
        with open(host_json, 'w') as f:
            f.write(get_host_json_template())


def _teardown_func_app(app_root):
    """Clean up after testing."""
    host_json = app_root / 'host.json'
    libraries_path = app_root / '.python_packages'
    
    # Only remove host.json and libraries path if they exist
    for path in (host_json, libraries_path):
        remove_path(path)


def retryable_test(
        number_of_retries: int,
        interval_sec: int,
        expected_exception: type = Exception
):
    """Decorator to retry a test multiple times if it fails."""
    def decorate(func):
        def call(*args, **kwargs):
            retries = number_of_retries
            while True:
                try:
                    return func(*args, **kwargs)
                except expected_exception as e:
                    retries -= 1
                    if retries <= 0:
                        raise e

                time.sleep(interval_sec)

        return call

    return decorate