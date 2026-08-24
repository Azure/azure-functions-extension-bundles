using NuGet.Common;
using NuGet.Credentials;
using NuGet.Protocol;
using NuGet.Protocol.Core.Types;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace Build
{
    public class Helper
    {
        public static async Task<string> GetLatestPackageVersion(string packageId, int majorVersion, bool isPrerelease = false)
        {
            DefaultCredentialServiceUtility.SetupDefaultCredentialService(NullLogger.Instance, nonInteractive: true);
            var repository = Repository.Factory.GetCoreV3(Settings.UpstreamPublicNuGetFeedUrl);
            var resource = await repository.GetResourceAsync<PackageMetadataResource>();

            var packages = await resource.GetMetadataAsync(packageId, includePrerelease: isPrerelease, includeUnlisted: false,
                new SourceCacheContext(), NullLogger.Instance, CancellationToken.None);

            var package = packages
                .OrderByDescending(p => p.Identity.Version)
                .FirstOrDefault(p => p.Identity.Version.Major == majorVersion);

            return package?.Identity.Version.OriginalVersion;
        }
    }
}
