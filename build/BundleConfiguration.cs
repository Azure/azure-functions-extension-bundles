using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Text;

namespace Build
{
    public sealed class BundleConfiguration
    {
        private static BundleConfiguration instance = null;

        public static BundleConfiguration Instance
        {
            get
            {
                if (instance == null)
                {
                    var configFileContent = FileUtility.ReadAllText(Settings.BundleConfigJsonFilePath);
                    instance = JsonConvert.DeserializeObject<BundleConfiguration>(configFileContent);
                }
                return instance;
            }
        }

        [JsonProperty("bundleId")]
        public string ExtensionBundleId { get; private set; }

        [JsonProperty("bundleVersion")]
        public string ExtensionBundleVersion { get; private set; }
    }
}