namespace Build
{
    public class IndexFileV2Metadata
    {
        public IndexFileV2Metadata(string endpointUrl, string bundleId)
        {
            EndPointUrl = endpointUrl;
            BundleId = bundleId;
            IndexV2FileName = $"{endpointUrl.Substring(8)}_{bundleId}_indexV2.json";
            IndexFileName = $"{endpointUrl.Substring(8)}_{bundleId}_index.json";
        }
        public string IndexV2FileName { get; private set; }

        public string IndexFileName { get; private set; }

        public string EndPointUrl { get; private set; }

        public string BundleId { get; private set; }

    }
}