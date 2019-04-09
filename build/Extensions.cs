using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Text;

namespace Build
{
    class Extensions
    {
        [JsonProperty(PropertyName = "id")]
        public string Id { get; set; }

        [JsonProperty(PropertyName = "version")]
        public string Version { get; set; }

    }
}
