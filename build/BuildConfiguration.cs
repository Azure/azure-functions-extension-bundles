using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace Build
{
    public class BuildConfiguration
    {
        public string ConfigurationName { get; set; } = string.Empty;

        public string ProjectFileName { get; set; }

        public string RuntimeIdentifier { get; set; } = string.Empty;

        public bool PublishReadyToRun { get; set; }

        public OSPlatform OSPlatform { get; internal set; }

        public string ConfigId => $"{ConfigurationName}_{RuntimeIdentifier}";

        public string GeneratedBundleZipFileName => $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}_{ConfigId}.zip";

        public string GeneratedBundleZipFilePath => Path.Combine(Settings.ArtifactsDirectory, GeneratedBundleZipFileName);

        public string PublishDirectoryPath => Path.Combine(Settings.RootBinDirectory, $"BundleProject_buildOutput_{ConfigId}");

        public string PublishBinariesPath => Path.Combine(PublishDirectoryPath, "bin");
    }
}