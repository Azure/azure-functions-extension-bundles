using System.IO;
using static Build.Settings;

namespace Build
{
    public class BuildConfiguration
    {
        public ConfigId ConfigId { get; set; }

        public string SourceProjectFileName { get; set; }

        public string RuntimeIdentifier { get; set; } = string.Empty;

        public bool PublishReadyToRun { get; set; }

        public string PublishDirectoryPath => Path.Combine(Settings.RootBinDirectory, $"{ConfigId}");

        public string PublishBinDirectoryPath => Path.Combine(PublishDirectoryPath, PublishBinDirectorySubPath);

        public string PublishBinDirectorySubPath { get; set; }
    }

}