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

        public static string[] nugetFeed = new[] { "https://www.nuget.org/api/v2/" };

        public static readonly string OutputDir = Path.Combine(Path.GetFullPath(".."), "artifacts");

        public static readonly string SrcProjectPath = Path.GetFullPath("../src/Microsoft.Azure.Functions.ExtensionBundle/");

        public static readonly string OutputProjectFile = Path.Combine(OutputDir, "extensions.csproj");
        public static readonly string ProjectFile = Path.Combine(SrcProjectPath, "extensions.csproj");

        public static readonly string ExtensionsJsonFile = Path.Combine(SrcProjectPath, "extensions.json");

        private static string config(string @default = null, string key = null)
        {
            var value = System.Environment.GetEnvironmentVariable(key);
            return string.IsNullOrEmpty(value)
                ? @default
                : value;
        }
    }
}