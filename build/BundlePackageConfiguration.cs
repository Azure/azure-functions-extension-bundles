using System.Collections.Generic;
using System.IO;
using static Build.Settings;

namespace Build
{
    public class BundlePackageConfiguration
    {
        public string PackageIdentifier { get; set; }

        public List<ConfigId> ConfigBinariesToInclude { get; set; } = new List<ConfigId>();

        public string BundleName => $"{BundleConfiguration.Instance.ExtensionBundleId}.{BundleConfiguration.Instance.ExtensionBundleVersion}_{PackageIdentifier}".Trim('_');

        public string GeneratedBundleZipFileName => $"{BundleName}.zip";

        public string GeneratedBundleZipFilePath => Path.Combine(ArtifactsDirectory, GeneratedBundleZipFileName);

        public string CsProjFilePath { get; set; }
    }

}