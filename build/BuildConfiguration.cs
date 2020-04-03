using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Build
{
    public class BuildConfiguration
    {
        public string ConfigurationName { get; set; }

        public string ProjectFileName { get; set; }

        public string RuntimeIdentifier { get; set; }

        public bool ReadyToRunEnabled { get; set; }
    }
}
