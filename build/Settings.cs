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

        public static BuildConfiguration netCoreV2BuildConfig = new BuildConfiguration()
        {
            ConfigurationName = "netCoreV2",
            ProjectFileName = "extensions.csproj",
            RuntimeIdentifier = "any"
        };

        public static BuildConfiguration netCoreV3RRWindowsX86BuildConfiguration = new BuildConfiguration()
        {
            ConfigurationName = "netCoreV3_RR",
            ProjectFileName = "extensions_netcoreapp3.csproj",
            RuntimeIdentifier = "win-x86",
            PublishReadyToRun = true,
            OSPlatform = OSPlatform.Windows
        };

        public static BuildConfiguration netCoreV3RRWindowsX64BuildConfiguration = new BuildConfiguration()
        {
            ConfigurationName = "netCoreV3_RR",
            ProjectFileName = "extensions_netcoreapp3.csproj",
            RuntimeIdentifier = "win-x64",
            PublishReadyToRun = true,
            OSPlatform = OSPlatform.Windows
        };


        public static BuildConfiguration netCoreV3RRLinuxBuildConfiguration = new BuildConfiguration()
        {
            ConfigurationName = "netCoreV3",
            ProjectFileName = "extensions_netcoreapp3.csproj",
            RuntimeIdentifier = "linux-x64",
            PublishReadyToRun = true,
            OSPlatform = OSPlatform.Linux
        };


        public static BuildConfiguration netCoreV3BuildConfiguration = new BuildConfiguration()
        {
            ConfigurationName = "netCoreV3",
            ProjectFileName = "extensions_netcoreapp3.csproj",
            RuntimeIdentifier = "any",
            OSPlatform = OSPlatform.Windows
        };

        public static readonly string SourcePath = Path.GetFullPath("../src/Microsoft.Azure.Functions.ExtensionBundle/");

        public static string ExtensionsJsonFilePath => Path.Combine(SourcePath, ExtensionsJsonFileName);

        public static string[] nugetFeed = new[] { "https://www.nuget.org/api/v2/" };

        public static readonly string StaticContentDirectoryName = "StaticContent";

        public static readonly string RootBinDirectory = Path.Combine(Path.GetFullPath(".."), "bin");

        public static readonly string ArtifactsDirectory = Path.Combine(Path.GetFullPath(".."), "artifacts");

        public static readonly string TemplatesRootDirectory = Path.Combine(RootBinDirectory, StaticContentDirectoryName, "v1");

        public static readonly string StaticContentDirectoryPath = Path.Combine(RootBinDirectory, StaticContentDirectoryName);

        public static readonly string TemplatesJsonFilePath = Path.Combine(TemplatesRootDirectory, "templates", "templates.json");

        public static readonly string ResourcesFilePath = Path.Combine(TemplatesRootDirectory, "resources", "Resources.json");

        public static readonly string ResourcesEnUSFilePath = Path.Combine(TemplatesRootDirectory, "resources", "Resources.en-US.json");

        public static readonly string ExtensionsJsonFileName = "extensions.json";

        public static string ExtensionBundleId = "Microsoft.Azure.Functions.ExtensionBundle";

        public static string ExtensionBundleVersionRange = "[2.*, 3.0.0)";

        public static string ExtensionBundleBuildVersion = "2.0.0";

        public static string TemplatesVersion = "2.0.1547";

        public static readonly string RUPackagePath = Path.Combine(RootBinDirectory, $"{ExtensionBundleId}.{ExtensionBundleBuildVersion}_RU_package", ExtensionBundleBuildVersion);

        public static readonly string IndexV2FileName = "index-v2.json";

        public static readonly string IndexFileName = "index.json";

        public static List<IndexFileV2Metadata> IndexFiles = new List<IndexFileV2Metadata>()
        {
            new IndexFileV2Metadata("https://functionscdnstaging.azureedge.net", ExtensionBundleId, "cdnStaging"),
            new IndexFileV2Metadata("https://functionscdn.azureedge.net", ExtensionBundleId, "cdnProd")
        };
    }
}