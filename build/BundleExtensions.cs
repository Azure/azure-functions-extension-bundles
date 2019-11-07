using System;
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json;

namespace Build
{
    class BundleExtensions
    {
        [JsonProperty(PropertyName = "Extensions")]
        public List<ExtensionInfo> Extensions { get; set; }
        public class ExtensionInfo
        {
            [JsonProperty(PropertyName = "name")]
            public string Name { get; set; }

            [JsonProperty(PropertyName = "typeName")]
            public string TypeName { get; set; }

            [JsonProperty(PropertyName = "bindings")]
            public List<string> Bindings { get; set; }
        }
    }
}
