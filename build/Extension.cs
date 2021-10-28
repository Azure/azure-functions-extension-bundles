﻿using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Text;

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

        [JsonProperty(PropertyName = "bindings")]
        public List<string> Bindings { get; set; }

        [JsonProperty(PropertyName = "minDotNetVersion")]
        public double? MinDotNetVersion { get; set; }
    }
}
