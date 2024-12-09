using System.Collections.Generic;

namespace Build
{
    public class IndexV2
    {
        public Dictionary<string, Dictionary<string, string>> BundleVersions { get; set; } = new Dictionary<string, Dictionary<string, string>>();

        public Template Templates { get; set; } = new Template();

        public class Template
        {
            public Dictionary<string, BundleResource> v1 { get; set; } = new Dictionary<string, BundleResource>();
        }

        public class BundleResource
        {
            public string Functions { get; set; }

            public string Bindings { get; set; }

            public string Resources { get; set; }
        }

        public bool TryAdd(string version, BundleResource resource)
        {
            var addSuccessful = BundleVersions.TryAdd(version,
                new Dictionary<string, string>()
                {
                    { "templates", version }
                });

            addSuccessful = addSuccessful && Templates.v1.TryAdd(version, resource);
            return addSuccessful;
        }
    }
}