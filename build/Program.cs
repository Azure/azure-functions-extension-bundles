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
                .Then(AddPackagesSources)
                .Then(BuildBundleBinariesForWindows)
                .Then(BuildBundleBinariesForLinux)
                .Then(GenerateNetCoreV2Bundle)
                .Then(GenerateNetCoreV3BundlesWindows)
                .Then(GenerateNetCoreV3BundlesLinux)
                 .Then(CreateRUPackage)
                 .Then(CreateCDNStoragePackage)
                 .Then(CreateCDNStoragePackageWindows)
                 .Then(CreateCDNStoragePackageLinux)
                .Run();
        }
    }
}
