using Build;
using System.Runtime.InteropServices;
using Xunit;
using static Build.BasePath;

namespace Microsoft.Azure.Functions.ExtensionBundle.Tests
{
    public class Fixture
    {
        public Fixture()
        {
            path = "../../../..";

            BuildSteps.Clean();
            BuildSteps.DownloadTemplates();

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                BuildSteps.BuildBundleBinariesForLinux();
            }
            else
            {
                BuildSteps.BuildBundleBinariesForWindows();
            }

        }
    }

    [CollectionDefinition("Fixture")]
    public class TestFixture : ICollectionFixture<Fixture>
    {
        // This class has no code, and is never created. Its purpose is simply
        // to be the place to apply [CollectionDefinition] and all the
        // ICollectionFixture<> interfaces.
    }
}
