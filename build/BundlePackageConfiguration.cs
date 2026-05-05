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
            return Path.Combine(Settings.RootBuildDirectory, ConfigId.any_any.ToString(), "extensions.csproj");
        }
    }

}