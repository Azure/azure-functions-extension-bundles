namespace Build
{
    public class IndexFileV2Metadata
    {
        public IndexFileV2Metadata(string endpointUrl, string bundleId)
        {
            EndPointUrl = endpointUrl;
            BundleId = bundleId;
            IndexFileDirectory = $"{endpointUrl.Substring(8)}_{bundleId}";
        }

        public string IndexFileDirectory { get; private set; }

        public string EndPointUrl { get; private set; }

        public string BundleId { get; private set; }

    }
}