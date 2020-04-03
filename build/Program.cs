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
                .Then(GenerateNetCoreV2Bundle)
                .Then(CreateRUPackage)
                .Then(CreateCDNStoragePackage)
                .Run();
        }
    }
}
