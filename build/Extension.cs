using Newtonsoft.Json;
using System.Collections.Generic;

namespace Build
{
    class Extension
    {
        [JsonProperty(PropertyName = "id")]
        public string Id { get; set; }

        [JsonProperty(PropertyName = "name")]
        public string Name { get; set; }

        [JsonProperty(PropertyName = "version")]
        public string Version { get; set; }

        [JsonProperty(PropertyName = "majorVersion")]
        public int MajorVersion { get; set; }

        [JsonProperty(PropertyName = "bindings")]
        public List<string> Bindings { get; set; }

        public override string ToString()
        {
            return $"{Id}, v{Version ?? MajorVersion.ToString()}";
        }
    }
}
