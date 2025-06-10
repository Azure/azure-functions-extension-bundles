# Overview

Extension bundles provide a way for non-.NET function apps to reference and use Azure Function extension packages written in C#. It bundles several of the Azure Function extensions into a single package which can then be referenced extension via the `host.json` file. Below is a sample configuration:

```Json
{
    "version": "2.0",
    "extensionBundle": {
        "id": "Microsoft.Azure.Functions.ExtensionBundle.Preview",
        "version": "[4.*, 5.0.0)"
    }
}
```

## Build status

|Branch|Status|
|------|------|
|main-preview|[![Build Status](https://azfunc.visualstudio.com/public/_apis/build/status/extension-bundles.public?branchName=main-preview)](https://azfunc.visualstudio.com/public/_build?definitionId=939&_a=summary&branchFilter=12530)|

## Build Requirements

- [Dotnet Core SDK 2.2](https://dotnet.microsoft.com/en-us/download/dotnet/2.2)
- [Dotnet Core SDK 3.1](https://dotnet.microsoft.com/en-us/download/dotnet/3.1)

## Local Build and Packaging

### Prerequisites

Before building locally, you need to obtain the latest template artifacts and place them in the `templatesArtifacts` directory at the repository root.

Required template files (example versions):

```
ExtensionBundle.Preview.v3.Templates.3.0.5130.zip
ExtensionBundle.Preview.v4.Templates.4.0.5130.zip
ExtensionBundle.v1.Templates.1.0.5130.zip
ExtensionBundle.v2.Templates.1.0.5130.zip
ExtensionBundle.v3.Templates.1.0.5130.zip
ExtensionBundle.v4.Templates.1.0.5130.zip
```

**How to obtain template artifacts:**

- Download the files from the [templates.public](https://dev.azure.com/azfunc/public/_build/results?buildId=221883) Pipeline

### Building on Windows

```powershell
# Set environment variables
$env:BUILD_REPOSITORY_LOCALPATH = "<ExtensionBundleRepoPath>"
$env:TEMPLATES_ARTIFACTS_DIRECTORY = "templatesArtifacts"

# Navigate to build directory and run
cd build
dotnet run skip:GenerateVulnerabilityReport,PackageNetCoreV3BundlesLinux,CreateCDNStoragePackageLinux,BuildBundleBinariesForLinux
```

### Building on Linux

```bash
# Set environment variables
export BUILD_REPOSITORY_LOCALPATH="<ExtensionBundleRepoPath>"
export TEMPLATES_ARTIFACTS_DIRECTORY="templatesArtifacts"

# Navigate to build directory and run
cd build
dotnet run skip:GenerateVulnerabilityReport,PackageNetCoreV3BundlesWindows,CreateRUPackage,CreateCDNStoragePackage,CreateCDNStoragePackageWindows,BuildBundleBinariesForWindows
```

**Note:** Replace `<ExtensionBundleRepoPath>` with the actual path to your extension bundle repository.


## Add extension

1. Identify the bundle version you want to update and checkout the corresponding branch

    |Bundle version | Branch |
    |------|------|
    | v1.x | https://github.com/Azure/azure-functions-extension-bundles/tree/v1.x |
    | v2.x | https://github.com/Azure/azure-functions-extension-bundles/tree/main-v2 |
    | v3.x | https://github.com/Azure/azure-functions-extension-bundles/tree/main-v3 |
    | v4.x-preview | https://github.com/Azure/azure-functions-extension-bundles/tree/main-preview |

2. Add the following details to [extensions.json](src/Microsoft.Azure.Functions.ExtensionBundle/extensions.json) file

    ```Javascript
    {
            "id": "Microsoft.Azure.WebJobs.Extensions.Kafka", // Nuget package id for the extension

            "majorVersion": "3",                              // Major version of the extension

            "name": "Kafka",                                  // This should match the name proprerty from bin/extensions.json in the generated output
                                                              // Easiest way to find out this is to perform the following steps.
                                                              // 1. Install the extension package to pre-compiled function app
                                                              // 2. Build the function app
                                                              // 3. Look at the bin/extension.json file in the output

            "bindings": [                                     // binding attributes supported by the extension.
                "kafkatrigger",
                "kafka"
            ]
        }
    ```

3. Build and test the extension bundle
4. To add a change or fix an issue that spans across multiple branches, try submitting the same set of commit hashes using `cherry-pick` in a pull request.

## Add template

- Follow the steps mentioned at the link below to add a template to extension bundle.
  - https://github.com/Azure/azure-functions-templates#adding-a-template-to-extension-bundle

- Also follow the steps mentioned at the link below to test templates added to extension bundle
  - https://github.com/Azure/azure-functions-templates#testing-script-type-template-via-core-tools

## Debugging the build process in Visual Studio

1. Open the `build/Build.sln` file in Visual Studio
1. Create a debug profile for the project (right-click on the project, "Properties", "Debug", "Open debug launch profiles UI")
1. Set the Command Line arguments using the instructions above (everything after `dotnet run`, i.e. `"skip:XXX,YYY,..."`)
1. Set the working directory to be the `build` directory
1. F5

## Test

1. Build extension bundles locally and locate the `artifacts\Microsoft.Azure.Functions.ExtensionBundle.{version}_any-any.zip` file.
2. Create a function app via core tools, open host.json to verify that it has extension bundle configuration present.
    - Sample commands for node app: `func init . --worker-runtime node`
3. Execute the `func GetExtensionBundlePath` to find the path to the bundle being used.
    - Sample response: `%userprofile%\.azure-functions-core-tools\Functions\ExtensionBundles\Microsoft.Azure.Functions.ExtensionBundle\2.8.4`
4. Replace the contents of the bundle directory from step 3 with the contents of the zip file from Step 1.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
