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
                .Then(CleanOutputDir)
                .Then(CreateOutputDir)
                .Then(AddPackages)
                .Run();
        }
    }
}
