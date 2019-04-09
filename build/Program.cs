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
                .Then(CleanOutputDirectory)
                .Then(CreateOutputDirectory)
                .Then(CopyProjectToOutputDirectory)
                .Then(AddPackages)
                .Then(BuildExtensionsProject)
                .Then(DownloadTemplates)
                //.Then(ExtractTemplatesToOutPutDirectory)
                //.Then(RemoveObjFolderFromOutPutDirectory)
                //.Then(ZipOutputDirectory)
                .Run();
        }
    }
}
