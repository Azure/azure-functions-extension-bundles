using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Build
{
    public static class Settings
    {
        public static string[] internalNugetFeed = new[]
        {
            "https://www.nuget.org/api/v2/",
            "https://www.myget.org/F/azure-appservice/api/v2",
            "https://www.myget.org/F/azure-appservice-staging/api/v2",
            "https://www.myget.org/F/fusemandistfeed/api/v2",
            "https://www.myget.org/F/30de4ee06dd54956a82013fa17a3accb/",
            "https://www.myget.org/F/xunit/api/v3/index.json",
            "https://dotnet.myget.org/F/aspnetcore-dev/api/v3/index.json"
        };

        public static readonly string SourcePath = Path.GetFullPath("../src/Microsoft.Azure.Functions.ExtensionBundle/");

        public static string ExtensionsJsonFilePath => Path.Combine(SourcePath, ExtensionsJsonFileName);

        public static string[] nugetFeed = new[]
        {
            "https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-net/nuget/v3/index.json",
            "https://www.nuget.org/api/v2/"
        };

        public static Dictionary<string, string> nugetSources = new Dictionary<string, string>()
        {
            { "azureSdk", "https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-net/nuget/v3/index.json"},
            { "nuget", "https://www.nuget.org/api/v2/"}
        };

        public static readonly string StaticContentDirectoryName = "StaticContent";

        public static readonly string RootBinDirectory = Path.Combine(Path.GetFullPath(".."), "bin");

        public static readonly string RootBuildDirectory = Path.Combine(Path.GetFullPath(".."), "build_temp");

        public static readonly string ArtifactsDirectory = Path.Combine(Path.GetFullPath(".."), "artifacts");

        public static readonly string TemplatesRootDirectory = Path.Combine(RootBinDirectory, StaticContentDirectoryName, "v1");

        public static readonly string StaticContentDirectoryPath = Path.Combine(RootBinDirectory, StaticContentDirectoryName);

        public static readonly string TemplatesJsonFilePath = Path.Combine(TemplatesRootDirectory, "templates", "templates.json");

        public static readonly string ResourcesFilePath = Path.Combine(TemplatesRootDirectory, "resources", "Resources.json");

        public static readonly string ResourcesEnUSFilePath = Path.Combine(TemplatesRootDirectory, "resources", "Resources.en-US.json");

        public static readonly string ExtensionsJsonFileName = "extensions.json";

        public static string ExtensionBundleId = "Microsoft.Azure.Functions.ExtensionBundle.Preview";

        public static string ExtensionBundleVersionRange = "[3.*, 4.0.0)";

        public static string ExtensionBundleBuildVersion = "3.0.0";

        public static string TemplatesVersion = "3.0.1850";

        public static readonly string RUPackagePath = Path.Combine(RootBinDirectory, $"{ExtensionBundleId}.{ExtensionBundleBuildVersion}_RU_package", ExtensionBundleBuildVersion);

        public static readonly string IndexV2FileName = "index-v2.json";

        public static readonly string IndexFileName = "index.json";

        public static List<IndexFileV2Metadata> IndexFiles = new List<IndexFileV2Metadata>()
        {
            new IndexFileV2Metadata("https://functionscdnstaging.azureedge.net", ExtensionBundleId, "cdnStaging"),
            new IndexFileV2Metadata("https://functionscdn.azureedge.net", ExtensionBundleId, "cdnProd")
        };

        public static List<BuildConfiguration> WindowsBuildConfigurations = new List<BuildConfiguration>()
        {
            new BuildConfiguration()
            {
                ConfigId = ConfigId.NetCoreApp2_any_any,
                SourceProjectFileName = "extensions.csproj",
                RuntimeIdentifier = "any",
                PublishReadyToRun = false,
                PublishBinDirectorySubPath = "bin"

            },
            new BuildConfiguration()
            {
                ConfigId = ConfigId.NetCoreApp3_win_x86,
                SourceProjectFileName = "extensions_netcoreapp3.csproj",
                RuntimeIdentifier = "win-x86",
                PublishReadyToRun = true,
                PublishBinDirectorySubPath = Path.Combine("bin_v3", "win-x86")
            },
            new BuildConfiguration()
            {
                ConfigId = ConfigId.NetCoreApp3_win_x64,
                SourceProjectFileName = "extensions_netcoreapp3.csproj",
                RuntimeIdentifier = "win-x64",
                PublishReadyToRun = true,
                PublishBinDirectorySubPath = Path.Combine("bin_v3", "win-x64")
            },
            new BuildConfiguration()
            {
                ConfigId = ConfigId.NetCoreApp3_any_any,
                SourceProjectFileName = "extensions_netcoreapp3.csproj",
                RuntimeIdentifier = "any",
                PublishReadyToRun = false,
                PublishBinDirectorySubPath = "bin"
            }
        };

        public static List<BuildConfiguration> LinuxBuildConfigurations = new List<BuildConfiguration>()
        {
            new BuildConfiguration()
            {
                ConfigId = ConfigId.NetCoreApp3_linux_x64,
                SourceProjectFileName = "extensions_netcoreapp3.csproj",
                RuntimeIdentifier = "linux-x64",
                PublishReadyToRun = true,
                PublishBinDirectorySubPath = Path.Combine("bin_v3", "linux-x64")
            },
            new BuildConfiguration()
            {
                ConfigId = ConfigId.NetCoreApp3_any_any,
                SourceProjectFileName = "extensions_netcoreapp3.csproj",
                RuntimeIdentifier = "any",
                PublishReadyToRun = false,
                PublishBinDirectorySubPath = "bin"
            }
        };

        public enum ConfigId
        {
            NetCoreApp3_win_x86,
            NetCoreApp3_win_x64,
            NetCoreApp2_any_any,
            NetCoreApp3_any_any,
            NetCoreApp3_linux_x64
        }

        public static BundlePackageConfiguration BundlePackageNetCoreV2Any = new BundlePackageConfiguration()
        {
            PackageIdentifier = string.Empty,
            ConfigBinariesToInclude = new List<ConfigId>() {
                ConfigId.NetCoreApp2_any_any
            },
            CsProjFilePath = Path.Combine(RootBuildDirectory, ConfigId.NetCoreApp2_any_any.ToString(), "extensions.csproj")
        };

        public static BundlePackageConfiguration BundlePackageNetCoreV3Any = new BundlePackageConfiguration()
        {
            PackageIdentifier = "any-any",
            ConfigBinariesToInclude = new List<ConfigId>() {
                ConfigId.NetCoreApp3_any_any
            },
            CsProjFilePath = Path.Combine(RootBuildDirectory, ConfigId.NetCoreApp3_any_any.ToString(), "extensions.csproj")
        };

        public static BundlePackageConfiguration BundlePackageNetCoreWindows = new BundlePackageConfiguration()
        {
            PackageIdentifier = "win-any",
            ConfigBinariesToInclude = new List<ConfigId>() {
                ConfigId.NetCoreApp2_any_any,
                ConfigId.NetCoreApp3_win_x86,
                ConfigId.NetCoreApp3_win_x64
            },
            CsProjFilePath = Path.Combine(RootBuildDirectory, ConfigId.NetCoreApp3_any_any.ToString(), "extensions.csproj")
        };

        public static BundlePackageConfiguration BundlePackageNetCoreV3Linux = new BundlePackageConfiguration()
        {
            PackageIdentifier = "linux-x64",
            ConfigBinariesToInclude = new List<ConfigId>() {
                ConfigId.NetCoreApp3_any_any,
                ConfigId.NetCoreApp3_linux_x64
            },
            CsProjFilePath = Path.Combine(RootBuildDirectory, ConfigId.NetCoreApp3_any_any.ToString(), "extensions.csproj")
        };
    }
}