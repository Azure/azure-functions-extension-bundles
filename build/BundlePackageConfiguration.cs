using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using static Build.Settings;

namespace Build
{
    public class BundlePackageConfiguration
    {
        public string PackageIdentifier { get; set; }

        public List<ConfigId> ConfigBinariesToInclude { get; set; } = new List<ConfigId>();

        public string OutputDirectoryPrefix { get; set; }

        public CompressionLevel CompressionLevel { get; set; } = CompressionLevel.NoCompression;

        public string BundleName => $"{BundleConfiguration.Instance.ExtensionBundleId}.{BundleConfiguration.Instance.ExtensionBundleVersion}_{PackageIdentifier}".Trim('_');

        public string GeneratedBundleZipFileName => $"{BundleName}.zip";

        public string GeneratedBundleZipFilePath => Path.Combine(ArtifactsDirectory, GeneratedBundleZipFileName);

        public string CsProjFilePath
        {
            get => _csProjFilePath ?? GetDefaultCsProjFilePath();
            set => _csProjFilePath = value;
        }

        private string _csProjFilePath;

        private string GetDefaultCsProjFilePath()
        {
            string configDir = OutputDirectoryPrefix != null
                ? $"{OutputDirectoryPrefix}_{ConfigId.any_any}"
                : ConfigId.any_any.ToString();
            return Path.Combine(Settings.RootBuildDirectory, configDir, "extensions.csproj");
        }
    }

}