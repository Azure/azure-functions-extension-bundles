using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;

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

        public static string[] nugetFeed = new[] { "https://www.nuget.org/api/v2/" };

        public static readonly string StaticContentDirectoryName = "StaticContent";

        public static readonly string RootBinDirectory = Path.Combine(Path.GetFullPath(".."), "bin");

        public static readonly string ArtifactsDirectory = Path.Combine(Path.GetFullPath(".."), "artifacts");

        public static readonly string TemplatesRootDirectory = Path.Combine(RootBinDirectory, StaticContentDirectoryName, "v1");

        public static readonly string StaticContentDirectoryPath = Path.Combine(RootBinDirectory, StaticContentDirectoryName);

        public static readonly string TemplatesJsonFilePath = Path.Combine(TemplatesRootDirectory, "Templates", "Templates.json");

        public static readonly string ResourcesFilePath = Path.Combine(TemplatesRootDirectory, "Resources", "Resources.json");

        public static readonly string ResourcesEnUSFilePath = Path.Combine(TemplatesRootDirectory, "Resources", "Resources.en-US.json");

        public static readonly string ExtensionsJsonFileName = "extensions.json";

        public static string ExtensionBundleId = "Microsoft.Azure.Functions.ExtensionBundle";

        public static string ExtensionBundleVersionRange = "[1.*, 2.0.0)";

        public static string ExtensionBundleBuildVersion = "1.2.0";

        public static string TemplatesVersion = "1.0.1543";

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