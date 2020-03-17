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
                .Then(CreateOutputDirectory)
                .Then(CopyProjectToOutputDirectory)
                .Then(AddPackages)
                .Then(BuildExtensionsProject)
                .Then(DownloadTemplates)
                .Then(RemoveObjFolderFromOutPutDirectory)
                .Then(CreateBundleJsonFile)
                .Then(AddBindingInfoToExtensionsJson)
                .Then(CreateBundleZipFile)
                .Then(CreateRUPackage)
                .Then(CreateCDNStoragePackage)
                .Run();
        }
    }
}
