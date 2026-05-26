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
            path = "../../../../..";

            BuildSteps.Clean();

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                BuildSteps.BuildLinuxBinaries();
            }
            else
            {
                BuildSteps.BuildPortableBinaries();
                BuildSteps.BuildWindowsBinaries();
                BuildSteps.BuildFilteredPortableBinaries();
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
