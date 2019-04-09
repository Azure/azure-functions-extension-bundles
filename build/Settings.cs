using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;

namespace Build
{
    public static class Settings
    {
        public static readonly string TemplatesZipUri = "https://functionscdn.azureedge.net/public/TemplatesApi/2.0.10344.zip";

        public static readonly string TemplatesDirectoryName = "StaticContent";

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

        public static string[] nugetFeed = new[] { "https://www.nuget.org/api/v2/" };

        public static readonly string SrcProjectPath = Path.GetFullPath("../src/Microsoft.Azure.Functions.ExtensionBundle/");

        public static readonly string ProjectFile = Path.Combine(SrcProjectPath, "extensions.csproj");

        public static readonly string OutputDirectory = Path.Combine(Path.GetFullPath(".."), "buildOutput");

        public static readonly string ArtifactsDirectory = Path.Combine(Path.GetFullPath(".."), "artifacts");

        public static readonly string BundleZipPath = Path.Combine(ArtifactsDirectory, $"{ExtensionBundleId}.");

        public static readonly string OutputTemplatesDirectory = Path.Combine(OutputDirectory, TemplatesDirectoryName);

        public static readonly string OutputTemplatesJsonFile = Path.Combine(OutputTemplatesDirectory, "Templates", "Templates.json");

        public static readonly string OutputProjectFile = Path.Combine(OutputDirectory, "extensions.csproj");

        public static readonly string OutputBinDirectory = Path.Combine(OutputDirectory, "bin");

        public static readonly string ExtensionsJsonFile = Path.Combine(SrcProjectPath, "extensions.json");

        public static string ExtensionBundleId = "Microsoft.Azure.Functions.ExtensionBundle";

        public static string ExtensionBundleVersionRange = "[1.*, 2.0.0)";

        public static string ExtensionBundleBuildVersion = "1.0.0";

        public static readonly string OutputBundleJsonFile= Path.Combine(OutputDirectory, "bundle.json");
    }
}