# How to Run Emulator Tests

This guide covers the complete setup and execution of emulator tests for Azure Functions Extension Bundles.

## About This Testing Framework

The original emulator test code is taken from [azure-functions-python-worker](https://github.com/Azure/azure-functions-python-worker) and unchanged the test code. We use it for testing extension bundle scenario.

**We modified the following:**

- **`test_setup.py`**: Changed the setup for extension bundle scenario
- **`testutils.py`**: Changed for core tools and extension bundle scenario

**Other utils and test code is unchanged from original.**

### Extension Bundle Version Testing

The test framework automatically references the `bundleVersion` from `src/Microsoft.Azure.Functions.ExtensionBundle/bundleConfig.json` and tests against that specific version. This ensures that:

- Tests use the exact same extension bundle version being built
- No manual version updates are needed in test files when the bundle version changes
- The `host.json` template in tests automatically uses the correct version from `bundleConfig.json`

**Example**: If `bundleConfig.json` contains `"bundleVersion": "4.25.0"`, the test framework will automatically configure functions to use extension bundle version `"4.25.0"`.

## CI/CD Integration

### Automated Testing in Azure DevOps

Emulator tests run automatically in the CI pipeline for:

- **All pull requests** to main, preview, and release branches
- **Main branch builds** and **preview branch builds**
- **Manual builds** (emulator tests are skipped for nightly scheduled builds)

The CI pipeline:

1. **Builds Linux extension bundles** as prerequisites
2. **Starts emulator services** using Docker Compose (Event Hubs, Storage, etc.)
3. **Sets up Python 3.12** environment with test dependencies
4. **Runs mock extension site** to simulate CDN behavior on port 8000
5. **Sets environment variables** including `FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI=http://localhost:8000`
6. **Executes emulator tests** with proper artifact collection
7. **Publishes test results** and debug artifacts to Azure DevOps

**CI Configuration Files:**

- [`eng/ci/templates/jobs/emulator-tests.yml`](../../eng/ci/templates/jobs/emulator-tests.yml) - Emulator test job template
- [`eng/public-build.yml`](../../eng/public-build.yml) - Public CI pipeline
- [`eng/official-build.yml`](../../eng/official-build.yml) - Official release pipeline

### Validating CI Setup Locally

Before pushing changes, validate your setup:

```bash
# Windows PowerShell
cd tests
.\validate-ci.ps1
```

These scripts check:

- Required files and dependencies
- Docker and Python availability
- bundleConfig.json validity
- CI template syntax

## Prerequisites

- **Python 3.12** installed
- **Docker Desktop** running (for storage emulator)
- **PowerShell** (recommended for Windows)
- **.NET 8 SDK** (for building extension bundles)

## Complete Setup Process

### 1. **Build and Package Extension Bundle**

Build the extension bundle locally. For detailed build instructions, see the "Local Build and Packaging" section in the main repository README.md.

**Quick build process:**

```powershell
# From the repository root
cd build
dotnet run skip:GenerateVulnerabilityReport,PackageNetCoreV3BundlesLinux,CreateCDNStoragePackageLinux,BuildBundleBinariesForLinux
```

This will generate extension bundle packages in the `artifacts/` directory.

**Note:** Ensure you have the required template artifacts in the `templatesArtifacts/` directory before building. See the main README.md for details on obtaining these files.

### 2. **Start Docker Storage Emulator**

Start the Docker-based storage emulator using Docker Compose:

```powershell
# Start Azurite storage emulator using Docker Compose
docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml up -d
docker compose -f tests/emulator_tests/utils/mysql/docker-compose.yml up -d

# This will start:
# - Azurite storage emulator on ports 10000, 10001, 10002
# - Event Hubs emulator (if needed for testing)

# To verify services are running
docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml ps
docker compose -f tests/emulator_tests/utils/mysql/docker-compose.yml ps

```

**To stop the services when done:**

```powershell
docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml down
docker compose -f tests/emulator_tests/utils/mysql/docker-compose.yml down

```

### 3. **Set Up Python Virtual Environment**

Create and activate a virtual environment:

```powershell
# Navigate to tests directory
cd tests

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Verify activation (you should see (venv) in your prompt)
```

### 4. **Install Python Dependencies**

```powershell
# Install with dev dependencies
cd tests
pip install -r requirements.txt

# This installs all required packages including:
# - pytest, requests, psutil
# - invoke (for task automation)
# - azure-functions and related packages
```

### 5. **Start Mock Extension Site**

Start the mock extension bundle download site:

```powershell
# Start mock site (serves extension bundles locally)
cd tests
python -m invoke -c test_setup mock-extension-site

# This will:
# - Create temporary directory structure
# - Copy extension bundles from artifacts/ 
# - Start HTTP server on localhost:3000
# - Display available download URLs
```

Keep this terminal running. The mock site serves extension bundles that your tests will download.

### 6. **Download and Extract Azure Functions Core Tools**

Run the webhost task to fetch and extract the latest Core Tools:

```powershell
# In a new terminal, with venv activated
python -m invoke -c test_setup webhost

# This will:
# - Download latest Azure Functions Core Tools
# - Extract to tests/build/webhost/
# - Make func.exe available for testing
```

### 7. **Configure Environment Variables**

Set up required environment variables:

```powershell
# Optional: Enable verbose output for debugging
$env:PYAZURE_WEBHOST_DEBUG = "true"

# Optional: Archive host logs for inspection
$env:ARCHIVE_WEBHOST_LOGS = "true"
```

### 8. **Run Tests**

Now you can run the emulator tests:

#### Run all emulator tests

```powershell
cd ..
python -m pytest tests/emulator_tests -v
```

#### Run a specific test file

```powershell
python -m pytest tests/emulator_tests/test_blob_functions.py -v
```

#### Run a specific test method

```powershell
python -m pytest tests/emulator_tests/test_blob_functions.py::TestBlobFunctions::test_blob_trigger -v
```

#### Run with extra verbose output

```powershell
python -m pytest tests/emulator_tests -v -s
```

#### Run with coverage report

```powershell
python -m pytest tests/emulator_tests --cov=utils --cov-report=html
```

## Quick Setup Script

For convenience, here's a PowerShell script that sets up everything:

```powershell
# Navigate to tests directory
Set-Location "C:\repo\azure-functions-extension-bundles\tests"

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Set environment variables
$env:PYAZURE_WEBHOST_DEBUG = "true"

# Start background services (run each in separate terminals)
Write-Host "Starting Docker services..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-Command", "docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml up -d"

Write-Host "Starting Mock Extension Site..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-Command", "cd C:\repo\azure-functions-extension-bundles\tests; .\venv\Scripts\Activate.ps1; python -m invoke -c test_setup mock-extension-site"

Write-Host "Setup complete! Wait a moment for services to start, then run tests." -ForegroundColor Yellow
Write-Host "Run tests with: python -m pytest tests/emulator_tests -v" -ForegroundColor Cyan
```

## Configuration Files

The test framework will automatically create configuration files to help with debugging:

- **`webhost_config.txt`**: Contains the exact command and environment variables used to start the Functions host
- **Host logs**: Available in temp files when `PYAZURE_WEBHOST_DEBUG=true`
- **Coverage reports**: Generated in `htmlcov/` when using `--cov` option

## Advanced Configuration

### Preview Extension Bundle Testing

To test with Preview extension bundles:

1. **Update bundleConfig.json**:

   ```json
   {
       "bundleId": "Microsoft.Azure.Functions.ExtensionBundle.Preview",
       "bundleVersion": "4.25.1",
       "templateVersion": "4.0.3043",
       "isPreviewBundle": true
   }
   ```

2. **Stop and restart the mock server**:

   ```powershell
   # Stop the current mock extension site (Ctrl+C in the terminal running it)
   
   # Restart with the updated configuration
   python -m invoke -c test_setup mock-extension-site
   ```

3. **Verify Preview bundle is being served**:
   - Check the mock server output for: `Microsoft.Azure.Functions.ExtensionBundle.Preview`
   - Verify the index URL: `http://localhost:3000/ExtensionBundles/Microsoft.Azure.Functions.ExtensionBundle.Preview/index.json`

**Note**: The test framework automatically detects whether you're using regular or Preview bundles based on the `bundleConfig.json` configuration and adjusts the host.json template accordingly.

### Custom Extension Bundle Versions

To test with specific extension bundle versions:

1. Place your custom `.zip` files in the `artifacts/` directory
2. Restart the mock extension site
3. The site will automatically detect and serve new versions

### Custom Core Tools Version

To use a specific Core Tools version:

```powershell
# Download specific version
python -m invoke -c test_setup webhost --webhost-version="4.0.5390"
```

### Port Configuration

If default ports conflict with other services:

```powershell
# Use custom port for mock extension site
python -m invoke -c test_setup mock-extension-site --port 3001

# Update environment variable accordingly
$env:FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI = "http://localhost:3001"
```

## Running Tests

## Using the Test Framework

The `testutils.py` module provides a comprehensive testing framework for Azure Functions Extension Bundles.

### Key Features

1. **Automatic Host Management**: Automatically starts and stops Azure Functions Core Tools
2. **Health Check Retries**: Implements intelligent health checks with retries
3. **Extension Bundle Integration**: Automatically configures extension bundle download from mock site
4. **Configuration Logging**: Writes detailed configuration to `webhost_config.txt` for debugging

### Example Test Class

```python
from utils.testutils import WebHostTestCase, retryable_test

class MyFunctionTest(WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return 'emulator_tests/my_function_app'
        
    @retryable_test(number_of_retries=3, interval_sec=1)
    def test_http_function(self):
        # Test HTTP trigger function
        r = self.webhost.request('get', 'HttpTrigger', params={'name': 'World'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('Hello World', r.text)
        
    def test_blob_function(self):
        # Test blob trigger function
        # Upload a test blob and verify function execution
        pass
```

### Test Framework Features

- **`WebHostTestCase`**: Base class that automatically manages Function Host lifecycle
- **`@retryable_test`**: Decorator for tests that may need multiple attempts
- **Health Checks**: Automatic health checking with configurable retries
- **Log Capture**: Automatic capture and archival of host logs
- **Environment Integration**: Seamless integration with mock extension site

## VS Code Debugging

The repository includes a pre-configured VS Code debug configuration for running and debugging emulator tests.

### Using the Existing Debug Configuration

The project includes a debug configuration in `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Debug Blob Function Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "purpose": ["debug-test"],
      "args": [
        "tests/emulator_tests/test_blob_functions.py",
        "-v"
      ],
      "python": "${workspaceFolder}\\venv\\Scripts\\python.exe",
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder};${workspaceFolder}\\tests",
        "AzureWebJobsStorage": "UseDevelopmentStorage=true",
        "FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI": "http://localhost:3000",
        "CORE_TOOLS_EXE_PATH": "${workspaceFolder}\\tests\\build\\webhost\\func.exe",
        "PYAZURE_WEBHOST_DEBUG": "true"
      },
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

### How to Debug Tests

1. **Prerequisites**: Ensure you've completed the setup steps (Docker services, virtual environment, Core Tools, etc.)

2. **Set Python Interpreter in VS Code**:

   ```text
   - Open Command Palette (Ctrl+Shift+P)
   - Type "Python: Select Interpreter"
   - Select the interpreter from your virtual environment: 
     `c:\repo\azure-functions-extension-bundles\tests\venv\Scripts\python.exe`
   ```

   **Note**: This step is crucial for VS Code to use the correct Python environment with all installed dependencies.

3. **Start Required Services**:

   ```powershell
   # Start Docker services (Azurite + Event Hubs emulator)
   docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml up -d
   
   # Start mock extension site
   python -m invoke -c test_setup mock-extension-site
   ```

4. **Open VS Code**: Open the repository root in VS Code

5. **Set Breakpoints**: Set breakpoints in your test files or in `utils/testutils.py`

6. **Run Debug Configuration**:
   - Press `F5` or go to **Run and Debug** panel
   - Select "Python: Debug Blob Function Tests"
   - Click the play button

### Creating Custom Debug Configurations

You can create additional debug configurations for different test files:

```json
{
  "name": "Python: Debug All Emulator Tests",
  "type": "python",
  "request": "launch",
  "module": "pytest",
  "purpose": ["debug-test"],
  "args": [
    "tests/emulator_tests",
    "-v", "-s"
  ],
  "python": "${workspaceFolder}\\venv\\Scripts\\python.exe",
  "cwd": "${workspaceFolder}",
  "env": {
    "PYTHONPATH": "${workspaceFolder};${workspaceFolder}\\tests",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI": "http://localhost:3000",
    "PYTHON_ISOLATE_WORKER_DEPENDENCIES":"1",
    "CORE_TOOLS_EXE_PATH": "${workspaceFolder}\\tests\\build\\webhost\\func.exe",
    "PYAZURE_WEBHOST_DEBUG": "true"
  },
  "console": "integratedTerminal",
  "justMyCode": false
}
```

### Debug Configuration Options

| Option | Purpose |
|--------|---------|
| `"purpose": ["debug-test"]` | Enables VS Code test discovery integration |
| `"python": "${workspaceFolder}\\venv\\Scripts\\python.exe"` | Uses the project's virtual environment |
| `"justMyCode": false` | Allows debugging into library code (azure-functions, etc.) |
| `"console": "integratedTerminal"` | Shows output in VS Code's integrated terminal |
| `"PYAZURE_WEBHOST_DEBUG": "true"` | Enables verbose Function Host logging |

### Debugging Tips

1. **Python Interpreter**: Always ensure VS Code is using the correct Python interpreter from your virtual environment:
   - Check the bottom-left corner of VS Code for the Python version
   - If it shows the wrong path, use `Ctrl+Shift+P` → "Python: Select Interpreter"
   - Select: `c:\repo\azure-functions-extension-bundles\tests\venv\Scripts\python.exe`

2. **Test Discovery**: With `"purpose": ["debug-test"]`, you can use VS Code's Test Explorer to run individual tests with debugging

3. **Function Host Debugging**: Set breakpoints in `utils/testutils.py` to debug Function Host startup and configuration

4. **Network Issues**: Enable verbose logging with `"PYAZURE_WEBHOST_DEBUG": "true"` to see detailed HTTP requests and responses

5. **Extension Bundle Downloads**: Debug extension bundle download issues by setting breakpoints in the mock extension site code

6. **Quick Test Debugging**: Use the Command Palette (`Ctrl+Shift+P`) and search for "Python: Debug Tests" to debug the current test file

7. **Import Errors**: If you see import errors during debugging, verify that:
   - The virtual environment is activated
   - VS Code is using the correct Python interpreter
   - All dependencies are installed with `cd tests && pip install -r requirements.txt`

## Troubleshooting

### Common Issues and Solutions

1. **Functions Host Not Found**:

   ```powershell
   # Ensure Core Tools is downloaded and extracted
   python -m invoke -c test_setup webhost
   
   # Verify the executable exists
   Test-Path "C:\repo\azure-functions-extension-bundles\tests\build\webhost\func.exe"
   
   # Set the environment variable explicitly
   $env:CORE_TOOLS_EXE_PATH = "C:\repo\azure-functions-extension-bundles\tests\build\webhost\func.exe"
   ```

2. **Mock Extension Site Connection Issues**:

   ```powershell
   # Check if mock site is running
   curl http://localhost:3000/ExtensionBundles/Microsoft.Azure.Functions.ExtensionBundle/index.json
   
   # Restart mock site if needed
   python -m invoke -c test_setup mock-extension-site
   ```

3. **Storage Connection Issues**:

   ```powershell
   # Ensure Docker services are running
   docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml ps
   
   # Start services if not running
   docker compose -f tests/emulator_tests/utils/eventhub/docker-compose.yml up -d
   
   # Verify storage connection
   $env:AzureWebJobsStorage = "UseDevelopmentStorage=true"
   ```

4. **Extension Bundle Download Failures**:

   ```powershell
   # Verify extension bundles exist in artifacts
   Get-ChildItem C:\repo\azure-functions-extension-bundles\artifacts\Microsoft.Azure.Functions.ExtensionBundle*.zip
   
   # Check mock site is serving correct URLs
   curl http://localhost:3000/ExtensionBundles/Microsoft.Azure.Functions.ExtensionBundle/4.24.1/Microsoft.Azure.Functions.ExtensionBundle.4.24.1_any-any.zip
   ```

5. **Python Virtual Environment Issues**:

   ```powershell
   # Verify virtual environment is activated
   which python  # Should point to venv/Scripts/python.exe
   
   # Reinstall dependencies if needed
   pip install -r requirements.txt --force-reinstall
   ```

6. **Port Conflicts**:

   ```powershell
   # Check what's using ports 3000 and 7071
   netstat -ano | findstr ":3000\|:7071"
   
   # Use custom ports if needed
   python -m invoke -c test_setup mock-extension-site --port 3001
   $env:FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI = "http://localhost:3001"
   ```

### Debug Information

When tests fail, check these files for detailed information:

- **`webhost_config.txt`**: In your function app directory, contains exact command used to start host
- **Host logs**: Temporary files when `PYAZURE_WEBHOST_DEBUG=true`
- **Test output**: Use `-v -s` flags with pytest for maximum verbosity

### Environment Variable Reference

| Variable | Purpose | Default Value |
|----------|---------|---------------|
| `CORE_TOOLS_EXE_PATH` | Path to func.exe | Auto-detected in build/webhost |
| `AzureWebJobsStorage` | Storage connection | `UseDevelopmentStorage=true` |
| `FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI` | Extension bundle source | `http://localhost:3000` |
| `PYAZURE_WEBHOST_DEBUG` | Enable verbose host output | `false` |
| `ARCHIVE_WEBHOST_LOGS` | Save host logs to files | `false` |

### Performance Tips

1. **Parallel Test Execution**:

   ```powershell
   # Run tests in parallel (be careful with shared resources)
   python -m pytest tests/emulator_tests -n auto
   ```

2. **Test Selection**:

   ```powershell
   # Run only fast tests
   python -m pytest tests/emulator_tests -m "not slow"
   
   # Run specific test patterns
   python -m pytest tests/emulator_tests -k "blob"
   ```

3. **Reuse Host Instance**:
   - The framework automatically reuses host instances within test classes
   - Group related tests in the same test class for better performance

## How to Add Emulator Tests

### 1. **Add Emulator Services**

Add required emulator services by creating Docker Compose configurations in the `utils/` directory:

```yaml
# Example: tests/emulator_tests/utils/your_service/docker-compose.yml
services:
  your-emulator:
    image: "mcr.microsoft.com/your-service-emulator:latest"
    ports:
      - "your_port:your_port"
    # ... other configuration
```

**Reference**: See `tests/emulator_tests/utils/eventhub/docker-compose.yml` for a complete example.

### 2. **Add Function Apps**

Create function apps with target trigger/input/output bindings:

```text
tests/emulator_tests/
├── your_extension_name/
│   ├── function_app.py       # Function implementation
├── utils
|   ├──your_extension
|   |    ├── docker-compose.yml # Setting up the emulator or docker container for extension dependencies
```

**Dependencies**: Add any additional dependencies to `tests/pyproject.toml` under the `[project.optional-dependencies]` dev section.

**Reference**: See `tests/emulator_tests/blob_functions/` directory structure for examples of various blob trigger, input, and output binding configurations.

### 3. **Add Test Cases**

Create test files following the naming pattern `test_*.py`:

```python
# tests/emulator_tests/test_your_functions.py
from utils.testutils import WebHostTestCase

class TestYourFunctions(WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return 'emulator_tests/your_functions'
    
    def test_your_function(self):
        # Your test implementation
        r = self.webhost.request('get', 'YourFunctionName')
        self.assertEqual(r.status_code, 200)
```

**Reference**: See `tests/emulator_tests/test_blob_functions.py` for comprehensive examples of testing various Azure Functions scenarios.

### 4. **Important Notes**

- **No host.json required**: The host.json file is automatically generated during test execution with the correct extension bundle configuration
- **Function metadata**: Use `function.json` files to define triggers, inputs, and outputs for each function
- **Test isolation**: Each test class gets its own Function Host instance for isolation
- **Emulator dependencies**: Ensure required emulators (Azurite, Event Hubs, etc.) are running before tests

### 5. **Test Structure Best Practices**

- Group related functions in the same directory (e.g., `blob_functions/`, `http_functions/`)
- Use descriptive test method names that indicate what scenario is being tested
- Include both positive and negative test cases
- Test different binding configurations (trigger, input, output)
- Verify both function execution and binding behavior

## Additional Resources

- [Main README.md](../../README.md): For building and packaging extension bundles
- [Core Tools Documentation](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- [Azurite Documentation](https://docs.microsoft.com/en-us/azure/storage/common/storage-use-azurite)
- [pytest Documentation](https://docs.pytest.org/)
