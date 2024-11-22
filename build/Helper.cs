using System;
using System.Net.Http;

namespace Build
{
    public class Helper
    {
        public static HttpClient HttpClient => _lazyClient.Value;

        private static Lazy<HttpClient> _lazyClient = new Lazy<HttpClient>(() =>
        {
            return new HttpClient(new HttpClientHandler
            {
                MaxConnectionsPerServer = 50
            });
        });
    }
}
