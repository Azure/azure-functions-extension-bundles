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
        private const string RUConfigPrefix = "ru";
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

        public static void BuildBundleBinariesForWindows()
        {
            Settings.WindowsBuildConfigurations.ForEach((config) => BuildExtensionsBundle(config).GetAwaiter().GetResult());
        }

        public static void BuildBundleBinariesForLinux()
        {
            Settings.LinuxBuildConfigurations.ForEach((config) => BuildExtensionsBundle(config).GetAwaiter().GetResult());
        }

        private static async Task<string> GenerateBundleProjectFile(BuildConfiguration buildConfig, string configPrefix = null, List<Extension> extensionList = null)
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

        private static async Task AddExtensionPackages(string projectFilePath, bool addPrereleasePackages, List<Extension> extensionList = null)
        {
            var extensions = extensionList ?? GetExtensionList();

            foreach (var extension in extensions)
            {
                string version = string.IsNullOrEmpty(extension.Version) ? await Helper.GetLatestPackageVersion(extension.Id, extension.MajorVersion, addPrereleasePackages) : extension.Version;
                Shell.Run("dotnet", $"add {projectFilePath} package {extension.Id} -v {version} -n");
            }
        }

        private static async Task BuildExtensionsBundle(BuildConfiguration buildConfig, string configPrefix = null, List<Extension> extensionList = null)
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
                    Settings.LinuxBuildConfigurations.FirstOrDefault(b => b.ConfigId == packageConfig);

                if (buildConfig == null)
                {
                    throw new InvalidOperationException($"Build configuration for ConfigId '{packageConfig}' not found.");
                }

                string sourceBinPath = bundlePackageConfig.OutputDirectoryPrefix != null
                    ? Path.Combine(Settings.RootBinDirectory, $"{bundlePackageConfig.OutputDirectoryPrefix}_{buildConfig.ConfigId}", buildConfig.PublishBinDirectorySubPath)
                    : buildConfig.PublishBinDirectoryPath;

                string targetBundleBinariesPath = Path.Combine(bundlePath, buildConfig.PublishBinDirectorySubPath);

                // Copy binaries
                FileUtility.CopyDirectory(sourceBinPath, targetBundleBinariesPath);

                string extensionJsonFilePath = Path.Join(targetBundleBinariesPath, Settings.ExtensionsJsonFileName);
                AddBindingInfoToExtensionsJson(extensionJsonFilePath);
            }

            // Copy templates (only if StaticContent directory exists)
            if (FileUtility.DirectoryExists(Settings.StaticContentDirectoryPath))
            {
                var staticContentDirectory = Path.Combine(bundlePath, Settings.StaticContentDirectoryName);
                FileUtility.CopyDirectory(Settings.StaticContentDirectoryPath, staticContentDirectory);
                Console.WriteLine($"Copied StaticContent from {Settings.StaticContentDirectoryPath}");
            }
            else
            {
                Console.WriteLine($"StaticContent directory not found at {Settings.StaticContentDirectoryPath}, skipping template copy for local development");
            }

            // Add bundle.json
            CreateBundleJsonFile(bundlePath);

            // Add Csproj file
            string projectPath = Path.Combine(bundlePath, "extensions.csproj");
            File.Copy(bundlePackageConfig.CsProjFilePath, projectPath);
        }

        public static void PackageNetCoreV3Bundle()
        {
            CreateExtensionBundle(Settings.BundlePackageNetCoreV3);
        }

        public static void PackageNetCoreV3BundlesLinux()
        {
            CreateExtensionBundle(Settings.BundlePackageNetCoreV3Linux);
        }

        public static void PackageNetCoreV3BundlesWindows()
        {
            CreateExtensionBundle(Settings.BundlePackageNetCoreV3Any);
            CreateExtensionBundle(Settings.BundlePackageNetCoreWindows);
        }

        public static void AddBundleZipFile(string rootPath, BundlePackageConfiguration packageConfig)
        {
            FileUtility.EnsureDirectoryExists(rootPath);
            string bundleZipDestinationPath = Path.Combine(rootPath, packageConfig.GeneratedBundleZipFileName);
            FileUtility.CopyFile(packageConfig.GeneratedBundleZipFilePath, bundleZipDestinationPath);
        }

        public static void CreateRUPackage()
        {
            if (Settings.RUExclusions.Length > 0)
            {
                Console.WriteLine($"Building RU package with exclusions: {string.Join(", ", Settings.RUExclusions)}");
            }

            // Always build RU self-contained (filtered extension list, own output dirs)
            var allExtensions = GetExtensionList();
            if (allExtensions == null || allExtensions.Count == 0)
            {
                throw new InvalidOperationException("Extension list is empty or could not be loaded.");
            }

            var filteredExtensions = allExtensions
                .Where(ext => !string.IsNullOrEmpty(ext.Id) && !Settings.RUExclusions.Contains(ext.Id, StringComparer.OrdinalIgnoreCase))
                .ToList();
            Console.WriteLine($"RU build: including {filteredExtensions.Count} of {allExtensions.Count} extensions");

            // Build Windows configs with filtered extension list
            Settings.WindowsBuildConfigurations.ForEach(config =>
                BuildExtensionsBundle(config, configPrefix: RUConfigPrefix, extensionList: filteredExtensions).GetAwaiter().GetResult());

            // Package into RU zip with version folder structure for downstream compatibility
            var ruPackageConfig = new BundlePackageConfiguration()
            {
                PackageIdentifier = RUPackageIdentifier,
                ConfigBinariesToInclude = Settings.BundlePackageNetCoreWindows.ConfigBinariesToInclude,
                OutputDirectoryPrefix = RUConfigPrefix,
                CompressionLevel = CompressionLevel.Optimal
            };

            CreateRUExtensionBundle(ruPackageConfig);
        }

        private static void CreateRUExtensionBundle(BundlePackageConfiguration bundlePackageConfig)
        {
            // Stage bundle content under <root>/<version>/ to match legacy RU zip layout
            string ruRootPath = Path.Combine(Settings.RootBuildDirectory, bundlePackageConfig.BundleName);
            if (Directory.Exists(ruRootPath))
            {
                Directory.Delete(ruRootPath, recursive: true);
            }
            string bundlePath = Path.Combine(ruRootPath, BundleConfiguration.Instance.ExtensionBundleVersion);

            StageBundleContent(bundlePackageConfig, bundlePath);

            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            // Zip from ruRootPath so the zip contains <version>/... at root
            ZipFile.CreateFromDirectory(ruRootPath, bundlePackageConfig.GeneratedBundleZipFilePath, bundlePackageConfig.CompressionLevel, false);
        }

        public static void CreateCDNStoragePackage()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                string directoryPath = Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory, BundleConfiguration.Instance.ExtensionBundleId);
                FileUtility.EnsureDirectoryExists(directoryPath);
                var bundleVersionDirectory = Path.Combine(directoryPath, BundleConfiguration.Instance.ExtensionBundleVersion);

                // Copy templates (only if StaticContent directory exists)
                if (FileUtility.DirectoryExists(Settings.StaticContentDirectoryPath))
                {
                    var contentDirectory = Path.Combine(bundleVersionDirectory, Settings.StaticContentDirectoryName);
                    FileUtility.CopyDirectory(Settings.StaticContentDirectoryPath, contentDirectory);
                    Console.WriteLine($"Copied StaticContent to CDN package at {contentDirectory}");
                }
                else
                {
                    Console.WriteLine($"StaticContent directory not found, skipping template copy for CDN package");
                }

                JsonConvert.DefaultSettings = () => new JsonSerializerSettings
                {
                    ContractResolver = new CamelCasePropertyNamesContractResolver()
                };

                // Generating v1 index file
                var indexFile = GetIndexFile($"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/index.json");
                indexFile.Add(BundleConfiguration.Instance.ExtensionBundleVersion);

                var indexFilePath = Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory, BundleConfiguration.Instance.ExtensionBundleId, Settings.IndexFileName);
                FileUtility.Write(indexFilePath, JsonConvert.SerializeObject(indexFile));

                AddBundleZipFile(bundleVersionDirectory, Settings.BundlePackageNetCoreV3);

                // Add bundle.json
                CreateBundleJsonFile(bundleVersionDirectory);

                // Add Csproj file
                string projectPath = Path.Combine(bundleVersionDirectory, "extensions.csproj");
                File.Copy(Settings.BundlePackageNetCoreV3.CsProjFilePath, projectPath);

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

                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackageNetCoreV3Any);
                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackageNetCoreWindows);

                string packageZipFilePath = Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}_windows.zip");
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

                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackageNetCoreV3Linux);

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
