using Colors.Net;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Newtonsoft.Json.Serialization;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Xml;

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
            string templatesZipUri = $"https://functionscdn.azureedge.net/public/ExtensionBundleTemplates/ExtensionBundle.v1.Templates.{Settings.TemplatesVersion}.zip";
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
            BuildConfiguration netCoreV2BuildConfiguration = new BuildConfiguration()
            {
                ConfigurationName = "netCoreV2",
                ProjectFileName = "extensions.csproj",
                RuntimeIdentifier = "any",
                ReadyToRunEnabled = false
            };

            var sourceProjectFilePath = GetSourceProjectFilePath(netCoreV2BuildConfiguration);
            var projectFilePath = GetProjectFilePath(netCoreV2BuildConfiguration);
            GenerateBundleProjectFile(sourceProjectFilePath, projectFilePath);

            var publishDirectory = GetProjectPublishPath(netCoreV2BuildConfiguration);
            BuildExtensionsProject(projectFilePath, publishDirectory, netCoreV2BuildConfiguration.ReadyToRunEnabled, netCoreV2BuildConfiguration.RuntimeIdentifier);

            var binariesPath = Path.Combine(publishDirectory, "bin");
            string bundlePath = CreateExtensionBundle(netCoreV2BuildConfiguration.ConfigurationName, binariesPath, projectFilePath);
            CreateBundleZipFile(bundlePath);
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

        public static void BuildExtensionsProject(string projectFilePath, string publishDirectory, bool readyToRunEnabled, string runtimeIdentifier)
        {
            var feeds = Settings.nugetFeed.Aggregate(string.Empty, (a, b) => $"{a} --source {b}");
            var publishCommandArguments = $"publish {projectFilePath} -c Release -o {publishDirectory}";

            if (readyToRunEnabled)
            {
                publishCommandArguments += $"-r {runtimeIdentifier}";
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

        public static string CreateExtensionBundle(string configurationName, string bundleBinariesDirectoryPath, string bundleProjectFilePath)
        {
            string bundleName = $"bundle_{configurationName}";
            // Create a directory to hold the bundle content
            string bundlePath = Path.Combine(Settings.RootBinDirectory, bundleName);
            string targetBundleBinariesPath = Path.Combine(bundlePath, "bin");

            // Copy binaries
            FileUtility.CopyDirectory(bundleBinariesDirectoryPath, targetBundleBinariesPath);

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

        public static void AddBundleContent(string rootPath)
        {
            string packagePath = Path.Combine(rootPath, Settings.ExtensionBundleBuildVersion);
            FileUtility.EnsureDirectoryExists(packagePath);

            // Copy the bundle zip
            string bundleZipFileName = $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}.zip";
            string bundlePath = Path.Combine(Settings.ArtifactsDirectory, bundleZipFileName);
            File.Copy(bundlePath, Path.Combine(packagePath, bundleZipFileName));

            // copy non binary files
            ZipFile.ExtractToDirectory(bundlePath, packagePath);
            FileUtility.DeleteDirectory(Path.Combine(packagePath, "bin"), true);
        }
        public static void CreateBundleZipFile(string bundleSourceDirectoryPath, string bundleNamePostFix = null)
        {
            string bundleName = $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}";
            bundleName += bundleNamePostFix == null ? ".zip" : $"_{bundleNamePostFix}.zip";

            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            string bundleZipFilePath = Path.Combine(Settings.ArtifactsDirectory, bundleName);
            ZipFile.CreateFromDirectory(bundleSourceDirectoryPath, bundleZipFilePath, CompressionLevel.NoCompression, false);
        }

        public static void CreateRUPackage()
        {
            FileUtility.EnsureDirectoryExists(Settings.RUPackagePath);
            // Copy the bundle zip
            string bundleZipFileName = $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}.zip";
            string bundlePath = Path.Combine(Settings.ArtifactsDirectory, bundleZipFileName);
            ZipFile.ExtractToDirectory(bundlePath, Settings.RUPackagePath);
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
                AddBundleContent(directoryPath);

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

        private static string GetProjectFilePath(BuildConfiguration buildConfiguration)
        {
            string bundleProjectDirectoryName = $"BundleProject_{buildConfiguration.ConfigurationName}_{buildConfiguration.RuntimeIdentifier}";
            var projectDirectory = Path.Combine(Settings.RootBinDirectory, bundleProjectDirectoryName);
            return Path.Combine(Settings.RootBinDirectory, projectDirectory, buildConfiguration.ProjectFileName);
        }

        private static string GetProjectPublishPath(BuildConfiguration buildConfiguration)
        {
            string bundleProjectDirectoryName = $"BundleProject_buildOutput_{buildConfiguration.ConfigurationName}_{buildConfiguration.RuntimeIdentifier}";
            return Path.Combine(Settings.RootBinDirectory, bundleProjectDirectoryName);
        }

        public static string GetSourceProjectFilePath(BuildConfiguration buildConfiguration) => Path.Combine(Settings.SourcePath, buildConfiguration.ProjectFileName);
    }
}
