using System;
using System.Linq;
using System.Net;
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
                .Then(DownloadManifestUtility)
                .Then(BuildBundleBinariesForWindows)
                .Then(BuildBundleBinariesForLinux)
                .Then(RunManifestUtilityWindows)
                .Then(RunManifestUtilityLinux)
                .Then(PackageNetCoreV3Bundle)
                .Then(PackageNetCoreV3BundlesWindows)
                .Then(PackageNetCoreV3BundlesLinux)
                .Then(CreateRUPackage)
                .Then(CreateCDNStoragePackage)
                .Then(CreateCDNStoragePackageWindows)
                .Then(CreateCDNStoragePackageLinux)
                .Run();
        }
    }
}