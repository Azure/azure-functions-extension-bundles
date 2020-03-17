namespace Build
{
    public class IndexFileV2Metadata
    {
        public IndexFileV2Metadata(string endpointUrl, string bundleId, string indexFileDirectory)
        {
            EndPointUrl = endpointUrl;
            BundleId = bundleId;
            IndexFileDirectory = indexFileDirectory;
        }

        public string IndexFileDirectory { get; private set; }

        public string EndPointUrl { get; private set; }

        public string BundleId { get; private set; }

    }
}