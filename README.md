# Overview
Extension bundle provides a way for non-dotnet function apps to reference and use to Azure Function extension packages written in C#. It does that by bundling several of the azure function extensions into a single package and then referencing extension bundle via host.json. Below is sample configuration for extension bundles.

```Json
{
    "version": "2.0",
    "extensionBundle": {
        "id": "Microsoft.Azure.Functions.ExtensionBundle",
        "version": "[2.*, 3.0.0)"
    }
}
```

## Build status
|Branch|Status|
|------|------|
|v1.x|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions/_apis/build/status/Azure.azure-functions-extension-bundles?branchName=v1.x)](https://azfunc.visualstudio.com/Azure%20Functions/_build?definitionId=41&_a=summary&repositoryFilter=26&branchFilter=509%2C509%2C509%2C509%2C509%2C509%2C509%2C509%2C509)|
|v2.x|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions/_apis/build/status/Azure.azure-functions-extension-bundles?branchName=v2.x)](https://azfunc.visualstudio.com/Azure%20Functions/_build?definitionId=41&_a=summary&repositoryFilter=26&branchFilter=865%2C865%2C865%2C865%2C865%2C865%2C865%2C865)|
|v3.x|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions/_apis/build/status/Azure.azure-functions-extension-bundles?branchName=v3.x)](https://azfunc.visualstudio.com/Azure%20Functions/_build?definitionId=41&_a=summary&repositoryFilter=26&branchFilter=1969%2C1969%2C1969%2C1969)|
|v3.x-preview|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions/_apis/build/status/Azure.azure-functions-extension-bundles?branchName=v3.x-preview)](https://azfunc.visualstudio.com/Azure%20Functions/_build?definitionId=41&_a=summary&repositoryFilter=26&branchFilter=3154)|
|v4.x-preview|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions/_apis/build/status/Azure.azure-functions-extension-bundles?branchName=v4.x-preview)](https://azfunc.visualstudio.com/Azure%20Functions/_build?definitionId=41&_a=summary&repositoryFilter=26&branchFilter=4220)|


## Build Requirements
- [Dotnet Core SDK 2.2](https://dotnet.microsoft.com/en-us/download/dotnet/2.2)
- [Dotnet Core SDK 3.1](https://dotnet.microsoft.com/en-us/download/dotnet/3.1)

## Build Steps

### Windows
```
cd build

dotnet run skip:PackageNetCoreV3BundlesLinux,CreateCDNStoragePackageLinux,BuildBundleBinariesForLinux,DownloadManifestUtility,RunManifestUtilityLinux,RunManifestUtilityWindows
```

### Linux
```
cd build

dotnet run skip:dotnet run skip:PackageNetCoreV2Bundle,PackageNetCoreV3BundlesWindows,CreateRUPackage,CreateCDNStoragePackage,CreateCDNStoragePackageWindows,BuildBundleBinariesForWindows,DownloadManifestUtility,RunManifestUtilityWindows,RunManifestUtilityLinux
```

## Add extension to a extension bundle
1. Identify the bundle version you want to update and checkout the corresponding branch

    |Bundle version | Branch |
    |------|------|
    | v1.x | https://github.com/Azure/azure-functions-extension-bundles/tree/v1.x |
    | v2.x | https://github.com/Azure/azure-functions-extension-bundles/tree/v2.x |
    | v3.x | https://github.com/Azure/azure-functions-extension-bundles/tree/v3.x |
    | v3.x-preview | https://github.com/Azure/azure-functions-extension-bundles/tree/v3.x-preview |
    | v4.x-preview | https://github.com/Azure/azure-functions-extension-bundles/tree/v4.x-preview |

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

## Add template to extension bundle.
- Follow the steps mentioned at the link below to add a template to extension bundle.
    - https://github.com/Azure/azure-functions-templates#adding-a-template-to-extension-bundle

- Also follow the steps mentioned at the link below to test templates added to extension bundle
    - https://github.com/Azure/azure-functions-templates#testing-script-type-template-via-core-tools


## Test an Extension Bundle
1. Build extension bundles locally and locate the `artifacts\Microsoft.Azure.Functions.ExtensionBundle.{version}_any-any.zip` file.
2. Create a function app via core tools, open host.json to verify that it has extension bundle configuration present.
    - Sample commands for node app: `func init . --worker-runtime node`
3. Execute the `func GetExtensionBundlePath` to find the path to the bundle being used.
    - Sample response: `%userprofile%\.azure-functions-core-tools\Functions\ExtensionBundles\Microsoft.Azure.Functions.ExtensionBundle\2.8.4`
4. Replace the contents of the bundle directory from step 3 with the contents of the zip file from Step 1.

# Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
