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
                .Then(BuildBundleBinariesForWindows)
                .Then(BuildBundleBinariesForLinux)
                .Then(PackageBundle)
                .Then(PackageBundlesWindows)
                .Then(PackageBundlesLinux)
                .Then(CreateRUPackage)
                .Then(CreateCDNStoragePackage)
                .Then(CreateCDNStoragePackageWindows)
                .Then(CreateCDNStoragePackageLinux)
                .Run();
        }
    }
}