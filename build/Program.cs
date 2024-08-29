﻿using System;
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
                .Then(GenerateVulnerabilityReport)
                .Then(PackageNetCoreV2Bundle)
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