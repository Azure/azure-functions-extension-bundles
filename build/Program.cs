using static Build.BuildSteps;

namespace Build
{
    class Program
    {
        static void Main(string[] args)
        {
            Orchestrator
                .CreateForTarget(args)
                .Then(Clean)
                .Then(DownloadTemplates)
                .Then(BuildPortableBinaries)
                .Then(BuildWindowsBinaries)
                .Then(BuildFilteredPortableBinaries)
                .Then(BuildLinuxBinaries)
                .Then(GenerateVulnerabilityReport)
                .Then(PackageBundle)
                .Then(PackagePortableBundle)
                .Then(PackageWindowsBundle)
                .Then(PackageLinuxBundle)
                .Then(CreateRUPackage)
                .Then(CreateCDNStoragePackage)
                .Then(CreateCDNStoragePackageWindows)
                .Then(CreateCDNStoragePackageLinux)
                .Run();
        }
    }
}