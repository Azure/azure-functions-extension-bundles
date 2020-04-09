using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace Build
{
    public class BuildConfiguration
    {
        public string ConfigurationName { get; set; }

        public string ProjectFileName { get; set; }

        public List<string> RuntimeIdentifiers { get; set; }

        public bool PublishReadyToRun { get; set; }

        public OSPlatform OSPlatform { get; internal set; }
    }
}
