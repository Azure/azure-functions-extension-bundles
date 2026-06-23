using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;

namespace Build
{
    public static class BuildSteps
    {
        private const string WindowsConfigPrefix = "win";
        private const string RUPackageIdentifier = "RU_package";

        public static void Clean()
        {
            if (FileUtility.DirectoryExists(Settings.RootBinDirectory))
            {
                Directory.Delete(Settings.RootBinDirectory, recursive: true);
            }

            if (FileUtility.DirectoryExists(Settings.RootBuildDirectory))
            {
                Directory.Delete(Settings.RootBuildDirectory, recursive: true);
            }

            if (FileUtility.DirectoryExists(Settings.ArtifactsDirectory))
            {
                Directory.Delete(Settings.ArtifactsDirectory, recursive: true);
            }

            if (FileUtility.DirectoryExists(Settings.ToolsDirectory))
            {
                Directory.Delete(Settings.ToolsDirectory, recursive: true);
            }
        }

        public static void DownloadTemplates()
        {
            bool isLocalBuild = string.IsNullOrEmpty(Environment.GetEnvironmentVariable("BUILD_BUILDID"));
            // Local package build requires DownloadTemplates operation. Put the value on the environment variable TEMPLATES_ARTIFACTS_DIRECTORY to skip the download operation.
            bool isLocalBuildWithTemplates = string.IsNullOrEmpty(Environment.GetEnvironmentVariable("TEMPLATES_ARTIFACTS_DIRECTORY"));
            if (isLocalBuild && isLocalBuildWithTemplates)
            {
                Console.WriteLine("Skipping template download for local build without templates artifacts directory.");
                return;
            }

            var files = Directory.GetFiles(Settings.TemplatesArtifactsDirectory);
            string previewStr = BundleConfiguration.Instance.IsPreviewBundle ? ".Preview" : String.Empty;
            string zipFileName = $"ExtensionBundle{previewStr}.v{BundleConfiguration.Instance.ExtensionBundleVersion[0]}.Templates";

            foreach (string file in files)
            {
                var fileName = Path.GetFileName(file);
                if (fileName.StartsWith(zipFileName))
                {
                    zipFileName = fileName;
                    break;
                }
            }

            Console.WriteLine($"Found matching templates in ${zipFileName}");

            string zipFilePath = Path.Combine(Settings.TemplatesArtifactsDirectory, zipFileName);
            FileUtility.EnsureDirectoryExists(Settings.TemplatesV1RootDirectory);
            ZipFile.ExtractToDirectory(zipFilePath, Settings.TemplatesV1RootDirectory);

            if (!FileUtility.DirectoryExists(Settings.TemplatesV1RootDirectory) || !FileUtility.FileExists(Settings.TemplatesJsonFilePath))
            {
                throw new Exception("Template download failed");
            }

            if (FileUtility.DirectoryExists(Settings.TemplatesV1RootDirectory) || FileUtility.FileExists(Settings.ResourcesFilePath))
            {
                FileUtility.CopyFile(Settings.ResourcesFilePath, Settings.ResourcesEnUSFilePath);
            }

            if (!FileUtility.DirectoryExists(Settings.TemplatesV1RootDirectory) || !FileUtility.FileExists(Settings.ResourcesEnUSFilePath))
            {
                throw new Exception("Resource Copy failed");
            }

            if (!FileUtility.DirectoryExists(Settings.TemplatesV2RootDirectory))
            {
                FileUtility.EnsureDirectoryExists(Settings.TemplatesV2RootDirectory);
            }

            if (FileUtility.DirectoryExists(Settings.TemplatesV2Directory))
            {
                Directory.Move(Settings.TemplatesV2Directory, Path.Join(Settings.TemplatesV2RootDirectory, "templates"));
            }

            if (FileUtility.DirectoryExists(Settings.ResourcesV2Directory))
            {
                Directory.Move(Settings.ResourcesV2Directory, Path.Join(Settings.TemplatesV2RootDirectory, "resources"));
            }

            if (FileUtility.DirectoryExists(Settings.BindingsV2Directory))
            {
                Directory.Move(Settings.BindingsV2Directory, Path.Join(Settings.TemplatesV2RootDirectory, "bindings"));
            }
        }

        public static void BuildPortableBinaries()
        {
            BuildExtensionsBundle(Settings.PortableBuildConfiguration).GetAwaiter().GetResult();
        }

        public static void BuildWindowsBinaries()
        {
            IList<Extension> filteredExtensions = GetFilteredWindowsExtensions();
            Settings.WindowsBuildConfigurations.ForEach((config) =>
                BuildExtensionsBundle(config, extensionList: filteredExtensions).GetAwaiter().GetResult());
        }

        public static void BuildFilteredPortableBinaries()
        {
            IList<Extension> filteredExtensions = GetFilteredWindowsExtensions();
            BuildExtensionsBundle(Settings.PortableBuildConfiguration, configPrefix: WindowsConfigPrefix, extensionList: filteredExtensions).GetAwaiter().GetResult();
        }

        public static void BuildLinuxBinaries()
        {
            Settings.LinuxBuildConfigurations.ForEach((config) => BuildExtensionsBundle(config).GetAwaiter().GetResult());
        }

        private static IList<Extension> GetFilteredWindowsExtensions()
        {
            var allExtensions = GetExtensionList();
            if (Settings.WindowsExclusions.Length == 0)
            {
                return allExtensions;
            }

            Console.WriteLine($"Applying Windows exclusions: {string.Join(", ", Settings.WindowsExclusions)}");
            var filtered = allExtensions
                .Where(ext => !string.IsNullOrEmpty(ext.Id) && !Settings.WindowsExclusions.Contains(ext.Id, StringComparer.OrdinalIgnoreCase))
                .ToList();
            Console.WriteLine($"Including {filtered.Count} of {allExtensions.Count} extensions");
            return filtered;
        }

        private static async Task<string> GenerateBundleProjectFile(BuildConfiguration buildConfig, string configPrefix = null, IList<Extension> extensionList = null)
        {
            var sourceNugetConfig = Path.Combine(Settings.SourcePath, Settings.NugetConfigFileName);
            var sourceProjectFilePath = Path.Combine(Settings.SourcePath, buildConfig.SourceProjectFileName);
            string configDirName = configPrefix != null ? $"{configPrefix}_{buildConfig.ConfigId}" : buildConfig.ConfigId.ToString();
            string projectDirectory = Path.Combine(Settings.RootBuildDirectory, configDirName);
            string targetProjectFilePath = Path.Combine(Settings.RootBuildDirectory, projectDirectory, "extensions.csproj");
            string targetNugetConfigFilePath = Path.Combine(Settings.RootBuildDirectory, projectDirectory, Settings.NugetConfigFileName);

            FileUtility.EnsureDirectoryExists(projectDirectory);
            FileUtility.CopyFile(sourceProjectFilePath, targetProjectFilePath);
            FileUtility.CopyFile(sourceNugetConfig, targetNugetConfigFilePath);

            await AddExtensionPackages(targetProjectFilePath, BundleConfiguration.Instance.IsPreviewBundle, extensionList);
            return targetProjectFilePath;
        }

        private static async Task AddExtensionPackages(string projectFilePath, bool addPrereleasePackages, IList<Extension> extensionList = null)
        {
            var extensions = extensionList ?? GetExtensionList();

            foreach (var extension in extensions)
            {
                string version = string.IsNullOrEmpty(extension.Version) ? await Helper.GetLatestPackageVersion(extension.Id, extension.MajorVersion, addPrereleasePackages) : extension.Version;
                Shell.Run("dotnet", $"add {projectFilePath} package {extension.Id} -v {version} -n");
            }
        }

        private static async Task BuildExtensionsBundle(BuildConfiguration buildConfig, string configPrefix = null, IList<Extension> extensionList = null)
        {
            var projectFilePath = await GenerateBundleProjectFile(buildConfig, configPrefix, extensionList);

            string publishPath = configPrefix != null
                ? Path.Combine(Settings.RootBinDirectory, $"{configPrefix}_{buildConfig.ConfigId}")
                : buildConfig.PublishDirectoryPath;

            string publishBinPath = configPrefix != null
                ? Path.Combine(publishPath, buildConfig.PublishBinDirectorySubPath)
                : buildConfig.PublishBinDirectoryPath;

            var publishCommandArguments = $"publish {projectFilePath} -c Release -o {publishPath}";

            if (!buildConfig.RuntimeIdentifier.Equals("any", StringComparison.OrdinalIgnoreCase))
            {
                publishCommandArguments += $" -r {buildConfig.RuntimeIdentifier}";
            }

            if (buildConfig.PublishReadyToRun)
            {
                publishCommandArguments += $" /p:PublishReadyToRun=true";
            }

            Shell.Run("dotnet", publishCommandArguments);

            if (Path.Combine(publishPath, "bin") != publishBinPath)
            {
                FileUtility.EnsureDirectoryExists(Directory.GetParent(publishBinPath).FullName);
                Directory.Move(Path.Combine(publishPath, "bin"), publishBinPath);
            }
        }

        public static void GenerateVulnerabilityReport()
        {
            RunVulnerabilityReport(Settings.PortableBuildConfiguration);
            Settings.WindowsBuildConfigurations.ForEach((config) => RunVulnerabilityReport(config));
        }

        public static void RunVulnerabilityReport(BuildConfiguration buildConfig)
        {
            string projectDirectory = Path.Combine(Settings.RootBuildDirectory, buildConfig.ConfigId.ToString());
            string projectFilePath = Path.Combine(Settings.RootBuildDirectory, projectDirectory, "extensions.csproj");

            var currectDirectory = Directory.GetCurrentDirectory();
            try
            {
                Directory.SetCurrentDirectory(Settings.RootBuildDirectory);

                Console.WriteLine(Directory.GetCurrentDirectory());
                Console.WriteLine($"dotnet list \"{projectFilePath}\" package --include-transitive --vulnerable");

                string output = Shell.GetOutput("dotnet", $"list \"{projectFilePath}\" package --include-transitive --vulnerable");

                if (!output.Contains("has no vulnerable packages given the current sources."))
                {
                    Console.WriteLine(output);
                    throw new Exception($"Vulnerabilities found in {projectFilePath}");
                }
            }
            finally
            {
                Directory.SetCurrentDirectory(currectDirectory);
            }

        }

        public static void AddBindingInfoToExtensionsJson(string extensionsJson)
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText(extensionsJson);
            var outputExtensions = JsonConvert.DeserializeObject<BundleExtensions>(extensionsJsonFileContent);
            var inputExtensions = GetExtensionList();

            foreach (var extensionJsonEntry in outputExtensions.Extensions)
            {
                extensionJsonEntry.Bindings = inputExtensions.Where(
                    e =>
                    {
                        return extensionJsonEntry.Name.Equals(e.Name, StringComparison.OrdinalIgnoreCase);
                    }).First().Bindings;
            }

            JsonConvert.DefaultSettings = () => new JsonSerializerSettings
            {
                ContractResolver = new CamelCasePropertyNamesContractResolver()
            };
            FileUtility.Write(extensionsJson, JsonConvert.SerializeObject(outputExtensions));
        }

        private static List<Extension> GetExtensionList()
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText(Settings.ExtensionsJsonFilePath);
            return JsonConvert.DeserializeObject<List<Extension>>(extensionsJsonFileContent);
        }

        public static void CreateExtensionBundle(BundlePackageConfiguration bundlePackageConfig)
        {
            // Create a directory to hold the bundle content
            string bundlePath = Path.Combine(Settings.RootBuildDirectory, bundlePackageConfig.BundleName);

            StageBundleContent(bundlePackageConfig, bundlePath);

            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            ZipFile.CreateFromDirectory(bundlePath, bundlePackageConfig.GeneratedBundleZipFilePath, bundlePackageConfig.CompressionLevel, false);
        }

        private static void StageBundleContent(BundlePackageConfiguration bundlePackageConfig, string bundlePath)
        {
            foreach (var packageConfig in bundlePackageConfig.ConfigBinariesToInclude)
            {
                // find the build configuration matching the config id
                var buildConfig = Settings.WindowsBuildConfigurations.FirstOrDefault(b => b.ConfigId == packageConfig) ??
                    Settings.LinuxBuildConfigurations.FirstOrDefault(b => b.ConfigId == packageConfig) ??
                    (Settings.PortableBuildConfiguration.ConfigId == packageConfig ? Settings.PortableBuildConfiguration : null);

                if (buildConfig == null)
                {
                    throw new InvalidOperationException($"Build configuration for ConfigId '{packageConfig}' not found.");
                }

                string sourceBinPath = buildConfig.PublishBinDirectoryPath;
                string targetBundleBinariesPath = Path.Combine(bundlePath, buildConfig.PublishBinDirectorySubPath);

                // Copy binaries
                FileUtility.CopyDirectory(sourceBinPath, targetBundleBinariesPath);

                string extensionJsonFilePath = Path.Join(targetBundleBinariesPath, Settings.ExtensionsJsonFileName);
                AddBindingInfoToExtensionsJson(extensionJsonFilePath);
            }

            StageCommonBundleFiles(bundlePath, bundlePackageConfig.CsProjFilePath);
        }

        public static void PackageBundle()
        {
            CreateExtensionBundle(Settings.BundlePackageBase);
        }

        public static void PackagePortableBundle()
        {
            CreateExtensionBundle(Settings.BundlePackagePortable);
        }

        public static void PackageLinuxBundle()
        {
            CreateExtensionBundle(Settings.BundlePackageLinux);
        }

        public static void PackageWindowsBundle()
        {
            string bundlePath = Path.Combine(Settings.RootBuildDirectory, Settings.BundlePackageWindows.BundleName);
            StageWindowsBundleContent(bundlePath);

            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            ZipFile.CreateFromDirectory(bundlePath, Settings.BundlePackageWindows.GeneratedBundleZipFilePath, CompressionLevel.NoCompression, false);
        }

        public static void AddBundleZipFile(string rootPath, BundlePackageConfiguration packageConfig)
        {
            FileUtility.EnsureDirectoryExists(rootPath);
            string bundleZipDestinationPath = Path.Combine(rootPath, packageConfig.GeneratedBundleZipFileName);
            FileUtility.CopyFile(packageConfig.GeneratedBundleZipFilePath, bundleZipDestinationPath);
        }

        public static void CreateRUPackage()
        {
            // RU package: same binaries as win-any.zip but with version-folder structure
            // and optimal compression for direct platform deployment.
            string ruBundleName = $"{BundleConfiguration.Instance.ExtensionBundleId}.{BundleConfiguration.Instance.ExtensionBundleVersion}_{RUPackageIdentifier}";
            string ruRootPath = Path.Combine(Settings.RootBuildDirectory, ruBundleName);
            if (Directory.Exists(ruRootPath))
            {
                Directory.Delete(ruRootPath, recursive: true);
            }
            string bundlePath = Path.Combine(ruRootPath, BundleConfiguration.Instance.ExtensionBundleVersion);

            StageWindowsBundleContent(bundlePath);

            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            string ruZipPath = Path.Combine(Settings.ArtifactsDirectory, $"{ruBundleName}.zip");
            ZipFile.CreateFromDirectory(ruRootPath, ruZipPath, CompressionLevel.Optimal, false);
        }

        /// <summary>
        /// Stages the Windows bundle content: win_x86/win_x64 from standard paths,
        /// filtered any_any from prefixed path, templates, bundle.json, and csproj.
        /// Used by both PackageWindowsBundle and CreateRUPackage.
        /// </summary>
        private static void StageWindowsBundleContent(string bundlePath)
        {
            // Stage win_x86 and win_x64 from standard paths
            foreach (var buildConfig in Settings.WindowsBuildConfigurations)
            {
                string sourceBinPath = buildConfig.PublishBinDirectoryPath;
                string targetBundleBinariesPath = Path.Combine(bundlePath, buildConfig.PublishBinDirectorySubPath);
                FileUtility.CopyDirectory(sourceBinPath, targetBundleBinariesPath);
                AddBindingInfoToExtensionsJson(Path.Join(targetBundleBinariesPath, Settings.ExtensionsJsonFileName));
            }

            // Stage filtered any_any from prefixed path
            var portableConfig = Settings.PortableBuildConfiguration;
            string filteredAnyBinPath = Path.Combine(Settings.RootBinDirectory, $"{WindowsConfigPrefix}_{portableConfig.ConfigId}", portableConfig.PublishBinDirectorySubPath);
            string targetPortableBinPath = Path.Combine(bundlePath, portableConfig.PublishBinDirectorySubPath);
            FileUtility.CopyDirectory(filteredAnyBinPath, targetPortableBinPath);
            AddBindingInfoToExtensionsJson(Path.Join(targetPortableBinPath, Settings.ExtensionsJsonFileName));

            // Use the filtered csproj (from win_any_any build) which excludes Fabric
            string filteredCsProjPath = Path.Combine(Settings.RootBuildDirectory, $"{WindowsConfigPrefix}_{portableConfig.ConfigId}", "extensions.csproj");
            StageCommonBundleFiles(bundlePath, filteredCsProjPath);
        }

        public static void CreateCDNStoragePackage()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                string directoryPath = Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory, BundleConfiguration.Instance.ExtensionBundleId);
                FileUtility.EnsureDirectoryExists(directoryPath);
                var bundleVersionDirectory = Path.Combine(directoryPath, BundleConfiguration.Instance.ExtensionBundleVersion);

                JsonConvert.DefaultSettings = () => new JsonSerializerSettings
                {
                    ContractResolver = new CamelCasePropertyNamesContractResolver()
                };

                // Generating v1 index file
                var indexFile = GetIndexFile($"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/index.json");
                indexFile.Add(BundleConfiguration.Instance.ExtensionBundleVersion);

                var indexFilePath = Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory, BundleConfiguration.Instance.ExtensionBundleId, Settings.IndexFileName);
                FileUtility.Write(indexFilePath, JsonConvert.SerializeObject(indexFile));

                AddBundleZipFile(bundleVersionDirectory, Settings.BundlePackageBase);
                StageCommonBundleFiles(bundleVersionDirectory, Settings.BundlePackageBase.CsProjFilePath);

                ZipFile.CreateFromDirectory(Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory), Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}.zip"), CompressionLevel.NoCompression, false);
            }
        }

        public static void CreateCDNStoragePackageWindows()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                string packageRootDirectoryPath = Path.Combine(Settings.RootBinDirectory, $"{indexFileMetadata.IndexFileDirectory}_windows");
                string packageBundleDirectory = Path.Combine(packageRootDirectoryPath, BundleConfiguration.Instance.ExtensionBundleId, BundleConfiguration.Instance.ExtensionBundleVersion);
                FileUtility.EnsureDirectoryExists(packageBundleDirectory);

                // Include the full unfiltered any-any.zip (all extensions including Fabric)
                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackagePortable);

                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackageWindows);

                string packageZipFilePath = Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}_windows.zip");
                FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
                ZipFile.CreateFromDirectory(packageRootDirectoryPath, packageZipFilePath, CompressionLevel.NoCompression, false);
            }
        }

        public static void CreateCDNStoragePackageLinux()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                string packageRootDirectoryPath = Path.Combine(Settings.RootBinDirectory, $"{indexFileMetadata.IndexFileDirectory}_linux");
                string packageBundleDirectory = Path.Combine(packageRootDirectoryPath, BundleConfiguration.Instance.ExtensionBundleId, BundleConfiguration.Instance.ExtensionBundleVersion);
                FileUtility.EnsureDirectoryExists(packageBundleDirectory);

                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackageLinux);

                string packageZipFilePath = Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}_linux.zip");
                ZipFile.CreateFromDirectory(packageRootDirectoryPath, packageZipFilePath, CompressionLevel.NoCompression, false);
            }
        }

        public static HashSet<string> GetIndexFile(string path)
        {
            using (var httpClient = new HttpClient())
            {
                var response = httpClient.GetAsync(path).Result;

                if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    return new HashSet<string>();
                }

                return JsonConvert.DeserializeObject<HashSet<string>>(response.Content.ReadAsStringAsync().Result);
            }
        }

        /// <summary>
        /// Stages common bundle files: StaticContent (templates), bundle.json, and extensions.csproj.
        /// </summary>
        private static void StageCommonBundleFiles(string bundlePath, string csProjPath)
        {
            if (FileUtility.DirectoryExists(Settings.StaticContentDirectoryPath))
            {
                var staticContentDirectory = Path.Combine(bundlePath, Settings.StaticContentDirectoryName);
                FileUtility.CopyDirectory(Settings.StaticContentDirectoryPath, staticContentDirectory);
                Console.WriteLine($"Copied StaticContent to {staticContentDirectory}");
            }
            else
            {
                Console.WriteLine($"StaticContent directory not found at {Settings.StaticContentDirectoryPath}, skipping template copy");
            }

            CreateBundleJsonFile(bundlePath);

            string projectPath = Path.Combine(bundlePath, "extensions.csproj");
            File.Copy(csProjPath, projectPath);
        }

        public static void CreateBundleJsonFile(string path)
        {
            var serializer = new JsonSerializerSettings();
            serializer.NullValueHandling = NullValueHandling.Ignore;
            Extension bundleInfo = new Extension()
            {
                Id = BundleConfiguration.Instance.ExtensionBundleId,
                Version = BundleConfiguration.Instance.ExtensionBundleVersion
            };
            var fileContents = JsonConvert.SerializeObject(bundleInfo, serializer);

            string bundleJsonPath = Path.Combine(path, "bundle.json");
            FileUtility.Write(bundleJsonPath, fileContents);
        }
    }
}
