using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Runtime.InteropServices;

namespace Build
{
    public static partial class BuildSteps
    {
        public static void Clean()
        {
            if (FileUtility.DirectoryExists(Settings.RootBinDirectory))
            {
                Directory.Delete(Settings.RootBinDirectory, recursive: true);
            }

            if (FileUtility.DirectoryExists(Settings.ArtifactsDirectory))
            {
                Directory.Delete(Settings.ArtifactsDirectory, recursive: true);
            }
        }

        public static void DownloadTemplates()
        {
            string downloadPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            FileUtility.EnsureDirectoryExists(downloadPath);
            string templatesZipUri = $"https://functionscdn.azureedge.net/public/ExtensionBundleTemplates/ExtensionBundle.v2.Templates.{Settings.TemplatesVersion}.zip";
            string zipFilePath = Path.Combine(downloadPath, $"templates.zip");
            var zipUri = new Uri(templatesZipUri);

            if (DownloadZipFile(zipUri, zipFilePath))
            {
                FileUtility.EnsureDirectoryExists(Settings.TemplatesRootDirectory);
                ZipFile.ExtractToDirectory(zipFilePath, Settings.TemplatesRootDirectory);
            }

            if (!FileUtility.DirectoryExists(Settings.TemplatesRootDirectory) || !FileUtility.FileExists(Settings.TemplatesJsonFilePath))
            {
                throw new Exception("Template download failed");
            }

            if (FileUtility.DirectoryExists(Settings.TemplatesRootDirectory) || FileUtility.FileExists(Settings.ResourcesFilePath))
            {
                FileUtility.CopyFile(Settings.ResourcesFilePath, Settings.ResourcesEnUSFilePath);
            }


            if (!FileUtility.DirectoryExists(Settings.TemplatesRootDirectory) || !FileUtility.FileExists(Settings.ResourcesEnUSFilePath))
            {
                throw new Exception("Resource Copy failed");
            }
        }

        public static void GenerateNetCoreV2Bundle()
        {
            GenerateBundle(Settings.netCoreV2BuildConfig);
        }

        public static void GenerateNetCoreV3BundlesWindows()
        {
            GenerateBundle(Settings.netCoreV3BuildConfiguration);
            GenerateBundle(Settings.netCoreV3RRWindowsX86BuildConfiguration);
            GenerateBundle(Settings.netCoreV3RRWindowsX64BuildConfiguration);
        }


        public static void GenerateNetCoreV3BundlesLinux()
        {
            GenerateBundle(Settings.netCoreV3RRLinuxBuildConfiguration);
        }

        public static void GenerateBundle(BuildConfiguration buildConfig)
        {
            var sourceProjectFilePath = Path.Combine(Settings.SourcePath, buildConfig.ProjectFileName);

            string bundleProjectDirectoryName = $"BundleProject_{buildConfig.ConfigId}";
            var projectDirectory = Path.Combine(Settings.RootBinDirectory, bundleProjectDirectoryName);
            string projectFilePath = Path.Combine(Settings.RootBinDirectory, projectDirectory, "extensions.csproj");

            GenerateBundleProjectFile(sourceProjectFilePath, projectFilePath);
            BuildExtensionsProject(projectFilePath, buildConfig);

            string bundlePath = CreateExtensionBundle(buildConfig, projectFilePath);
            CreateBundleZipFile(bundlePath, buildConfig.ConfigId);

        }

        public static void GenerateBundleProjectFile(string sourceProjectFilePath, string targetProjectFilePath)
        {
            var projectDirectory = Path.GetDirectoryName(targetProjectFilePath);
            FileUtility.EnsureDirectoryExists(projectDirectory);
            FileUtility.CopyFile(sourceProjectFilePath, targetProjectFilePath);
            AddExtensionPackages(targetProjectFilePath);
        }

        public static void AddExtensionPackages(string projectFilePath)
        {
            var extensions = GetExtensionList();
            foreach (var extension in extensions)
            {
                Shell.Run("dotnet", $"add {projectFilePath} package {extension.Id} -v {extension.Version} -n");
            }
        }

        public static void BuildExtensionsProject(string projectFilePath, BuildConfiguration buildConfig)
        {
            var feeds = Settings.nugetFeed.Aggregate(string.Empty, (a, b) => $"{a} --source {b}");
            var publishCommandArguments = $"publish {projectFilePath} -c Release -o {buildConfig.PublishDirectoryPath}";

            if (!buildConfig.RuntimeIdentifier.Equals("any", StringComparison.OrdinalIgnoreCase))
            {
                publishCommandArguments += $" -r {buildConfig.RuntimeIdentifier}";
            }

            if (buildConfig.PublishReadyToRun)
            {
                publishCommandArguments += $" /p:PublishReadyToRun=true";
            }

            Shell.Run("dotnet", publishCommandArguments);
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

        public static bool DownloadZipFile(Uri zipUri, string filePath)
        {
            using (var httpClient = new HttpClient())
            {
                var response = httpClient.GetAsync(zipUri).GetAwaiter().GetResult();
                if (!response.IsSuccessStatusCode)
                {
                    return false;
                }

                var content = response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult();
                var stream = new FileStream(filePath, FileMode.Create, FileAccess.Write, FileShare.None, bufferSize: 4096, useAsync: true);
                stream.Write(content);
                stream.Close();
            }
            return true;
        }

        public static string CreateExtensionBundle(BuildConfiguration buildConfig, string bundleProjectFilePath)
        {
            string bundleName = $"bundle_{buildConfig.ConfigId}";
            // Create a directory to hold the bundle content
            string bundlePath = Path.Combine(Settings.RootBinDirectory, bundleName);
            string targetBundleBinariesPath = Path.Combine(bundlePath, "bin");

            // Copy binaries
            FileUtility.CopyDirectory(buildConfig.PublishBinariesPath, targetBundleBinariesPath);

            // Copy templates
            var staticContentDirectory = Path.Combine(bundlePath, Settings.StaticContentDirectoryName);
            FileUtility.CopyDirectory(Settings.StaticContentDirectoryPath, staticContentDirectory);

            // Add bundle.json
            CreateBundleJsonFile(bundlePath);

            // Add Csproj file
            string projectPath = Path.Combine(bundlePath, "extensions.csproj");
            string extensionJsonFilePath = Path.Join(targetBundleBinariesPath, Settings.ExtensionsJsonFileName);
            AddBindingInfoToExtensionsJson(extensionJsonFilePath);
            File.Copy(bundleProjectFilePath, projectPath);
            return bundlePath;
        }

        public static void AddBundleZipFile(string rootPath, BuildConfiguration buildConfig, string updatedbundleFileName = null)
        {
            string bundleFileZipFileName = updatedbundleFileName ?? buildConfig.GeneratedBundleZipFileName;
            string bundleZipDestinationPath = Path.Combine(rootPath, bundleFileZipFileName);
            FileUtility.CopyFile(buildConfig.GeneratedBundleZipFilePath, bundleZipDestinationPath);
        }

        public static void CreateBundleZipFile(string bundleSourceDirectoryPath, string configId)
        {
            string bundleName = $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}_{configId}.zip";
            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            string bundleZipFilePath = Path.Combine(Settings.ArtifactsDirectory, bundleName);
            ZipFile.CreateFromDirectory(bundleSourceDirectoryPath, bundleZipFilePath, CompressionLevel.NoCompression, false);
        }

        public static void CreateRUPackage()
        {
            FileUtility.EnsureDirectoryExists(Settings.RUPackagePath);

            ZipFile.ExtractToDirectory(Settings.netCoreV2BuildConfig.GeneratedBundleZipFilePath, Settings.RUPackagePath);

            // add v3 binaires
            string ruPackageBinX86DirectoryPath = Path.Combine(Settings.RUPackagePath, $"v3/bin-{Settings.netCoreV3RRWindowsX86BuildConfiguration.RuntimeIdentifier}");
            FileUtility.CopyDirectory(Settings.netCoreV3RRWindowsX86BuildConfiguration.PublishBinariesPath, ruPackageBinX86DirectoryPath);

            string ruPackageBinX64DirectoryPath = Path.Combine(Settings.RUPackagePath, $"v3/bin-{Settings.netCoreV3RRWindowsX64BuildConfiguration.RuntimeIdentifier}");
            FileUtility.CopyDirectory(Settings.netCoreV3RRWindowsX64BuildConfiguration.PublishBinariesPath, ruPackageBinX64DirectoryPath);

            var RURootPackagePath = Directory.GetParent(Settings.RUPackagePath);
            ZipFile.CreateFromDirectory(RURootPackagePath.FullName, Path.Combine(Settings.ArtifactsDirectory, $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}_RU_package.zip"), CompressionLevel.NoCompression, false);
        }

        public static void CreateCDNStoragePackage()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                // Generating v2 index file
                var indexV2File = GetIndexV2File($"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/index-v2.json");
                var bundleResource = new IndexV2.BundleResource()
                {
                    Bindings = $"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/{Settings.ExtensionBundleBuildVersion}/StaticContent/v1/bindings/bindings.json",
                    Functions = $"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/{Settings.ExtensionBundleBuildVersion}/StaticContent/v1/templates/templates.json",
                    Resources = $"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/{Settings.ExtensionBundleBuildVersion}/StaticContent/v1/resources/" + "Resources.{locale}.json"
                };

                indexV2File.TryAdd(Settings.ExtensionBundleBuildVersion, bundleResource);

                // write index-v2 file
                string directoryPath = Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory, Settings.ExtensionBundleId);
                FileUtility.EnsureDirectoryExists(directoryPath);

                var bundleVersionDirectory = Path.Combine(directoryPath, Settings.ExtensionBundleBuildVersion);
                var contentDirectory = Path.Combine(bundleVersionDirectory, Settings.StaticContentDirectoryName);
                FileUtility.CopyDirectory(Settings.StaticContentDirectoryPath, contentDirectory);

                // Add bundle.json
                CreateBundleJsonFile(bundleVersionDirectory);

                // Add Csproj file
                string destinationProjectPath = Path.Combine(bundleVersionDirectory, "extensions.csproj");

                string bundleProjectDirectoryName = $"BundleProject_{Settings.netCoreV2BuildConfig.ConfigId}";
                var projectDirectory = Path.Combine(Settings.RootBinDirectory, bundleProjectDirectoryName);
                string projectFilePath = Path.Combine(Settings.RootBinDirectory, projectDirectory, "extensions.csproj");
                File.Copy(projectFilePath, destinationProjectPath);


                AddBundleZipFile(bundleVersionDirectory, Settings.netCoreV2BuildConfig, $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}.zip");

                var indexV2FilePath = Path.Combine(directoryPath, Settings.IndexV2FileName);
                JsonConvert.DefaultSettings = () => new JsonSerializerSettings
                {
                    ContractResolver = new CamelCasePropertyNamesContractResolver()
                };

                FileUtility.Write(indexV2FilePath, JsonConvert.SerializeObject(indexV2File));

                // Generating v1 index file
                var indexFile = GetIndexFile($"{indexFileMetadata.EndPointUrl}/public/ExtensionBundles/{indexFileMetadata.BundleId}/index.json");
                indexFile.Add(Settings.ExtensionBundleBuildVersion);

                var indexFilePath = Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory, Settings.ExtensionBundleId, Settings.IndexFileName);
                FileUtility.Write(indexFilePath, JsonConvert.SerializeObject(indexFile));
                ZipFile.CreateFromDirectory(Path.Combine(Settings.RootBinDirectory, indexFileMetadata.IndexFileDirectory), Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}.zip"), CompressionLevel.NoCompression, false);
            }
        }

        public static void CreateCDNStoragePackageWindows()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                string packageRootDirectoryPath = Path.Combine(Settings.RootBinDirectory, $"{indexFileMetadata.IndexFileDirectory}_windows");
                string packageBundleDirectory = Path.Combine(packageRootDirectoryPath, Settings.ExtensionBundleId, Settings.ExtensionBundleBuildVersion);
                FileUtility.EnsureDirectoryExists(packageBundleDirectory);

                AddBundleZipFile(packageBundleDirectory, Settings.netCoreV3RRWindowsX64BuildConfiguration);
                AddBundleZipFile(packageBundleDirectory, Settings.netCoreV3RRWindowsX86BuildConfiguration);
                AddBundleZipFile(packageBundleDirectory, Settings.netCoreV3BuildConfiguration);

                string packageZipFilePath = Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}_windows.zip");
                ZipFile.CreateFromDirectory(packageRootDirectoryPath, packageZipFilePath, CompressionLevel.NoCompression, false);
            }
        }

        public static void CreateCDNStoragePackageLinux()
        {
            foreach (var indexFileMetadata in Settings.IndexFiles)
            {
                string packageRootDirectoryPath = Path.Combine(Settings.RootBinDirectory, $"{indexFileMetadata.IndexFileDirectory}_linux");
                string packageBundleDirectory = Path.Combine(packageRootDirectoryPath, Settings.ExtensionBundleId, Settings.ExtensionBundleBuildVersion);
                FileUtility.EnsureDirectoryExists(packageBundleDirectory);

                AddBundleZipFile(packageBundleDirectory, Settings.netCoreV3RRLinuxBuildConfiguration);

                string packageZipFilePath = Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}_linux.zip");
                ZipFile.CreateFromDirectory(packageZipFilePath, packageZipFilePath, CompressionLevel.NoCompression, false);
            }
        }

        public static IndexV2 GetIndexV2File(string path)
        {
            using (var httpClient = new HttpClient())
            {
                var response = httpClient.GetAsync(path).Result;

                if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    return new IndexV2();
                }

                return JsonConvert.DeserializeObject<IndexV2>(response.Content.ReadAsStringAsync().Result);
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
                Id = Settings.ExtensionBundleId,
                Version = Settings.ExtensionBundleBuildVersion
            };
            var fileContents = JsonConvert.SerializeObject(bundleInfo, serializer);

            string bundleJsonPath = Path.Combine(path, "bundle.json");
            FileUtility.Write(bundleJsonPath, fileContents);
        }
    }
}
