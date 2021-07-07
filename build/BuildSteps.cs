using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;

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

            if (FileUtility.DirectoryExists(Settings.RootBuildDirectory))
            {
                Directory.Delete(Settings.RootBuildDirectory, recursive: true);
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
            string templatesZipUri = $"https://functionscdn.azureedge.net/public/ExtensionBundleTemplates/ExtensionBundle.Preview.v3.Templates.{Settings.TemplatesVersion}.zip";
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

        public static void BuildBundleBinariesForWindows()
        {
            Settings.WindowsBuildConfigurations.ForEach((config) => BuildExtensionsBundle(config));

            // temporary fix for missing extensions.json
            string sourceExtensionsJsonPath = Path.Combine(Settings.RootBinDirectory, @"NetCoreApp3_win_x64\bin_v3\win-x64\extensions.json");
            string extensionsJsonPath = Path.Combine(Settings.RootBinDirectory, @"NetCoreApp3_win_x86\bin_v3\win-x86\extensions.json");
            File.Copy(sourceExtensionsJsonPath, extensionsJsonPath, true);
        }

        public static void BuildBundleBinariesForLinux()
        {
            Settings.LinuxBuildConfigurations.ForEach((config) => BuildExtensionsBundle(config));
        }

        public static string GenerateBundleProjectFile(BuildConfiguration buildConfig)
        {
            var sourceProjectFilePath = Path.Combine(Settings.SourcePath, buildConfig.SourceProjectFileName);
            string projectDirectory = Path.Combine(Settings.RootBuildDirectory, buildConfig.ConfigId.ToString());
            string targetProjectFilePath = Path.Combine(Settings.RootBuildDirectory, projectDirectory, "extensions.csproj");

            FileUtility.EnsureDirectoryExists(projectDirectory);
            FileUtility.CopyFile(sourceProjectFilePath, targetProjectFilePath);
            AddExtensionPackages(targetProjectFilePath);
            return targetProjectFilePath;
        }

        public static void AddExtensionPackages(string projectFilePath)
        {
            var extensions = GetExtensionList();
            foreach (var extension in extensions)
            {
                Shell.Run("dotnet", $"add {projectFilePath} package {extension.Id} -v {extension.Version} -n");
            }
        }

        public static void AddPackagesSources()
        {
            var extensions = GetExtensionList();
            foreach (var extension in Settings.nugetSources)
            {
                try
                {
                    Shell.Run("dotnet", $"nuget add source {extension.Value} -n {extension.Key}");
                }
                catch (Exception e)
                {
                    Console.WriteLine(e.Message);
                }

            }
        }

        public static void BuildExtensionsBundle(BuildConfiguration buildConfig)
        {
            var projectFilePath = GenerateBundleProjectFile(buildConfig);

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

            if (Path.Combine(buildConfig.PublishDirectoryPath, "bin") != buildConfig.PublishBinDirectoryPath)
            {
                FileUtility.EnsureDirectoryExists(Directory.GetParent(buildConfig.PublishBinDirectoryPath).FullName);
                Directory.Move(Path.Combine(buildConfig.PublishDirectoryPath, "bin"), buildConfig.PublishBinDirectoryPath);
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

        public static void CreateExtensionBundle(BundlePackageConfiguration bundlePackageConfig)
        {
            // Create a directory to hold the bundle content
            string bundlePath = Path.Combine(Settings.RootBuildDirectory, bundlePackageConfig.BundleName);

            foreach (var packageConfig in bundlePackageConfig.ConfigBinariesToInclude)
            {
                // find the build configuration matching the config id
                var buildConfig = Settings.WindowsBuildConfigurations.FirstOrDefault(b => b.ConfigId == packageConfig) ??
                    Settings.LinuxBuildConfigurations.FirstOrDefault(b => b.ConfigId == packageConfig);

                string targetBundleBinariesPath = Path.Combine(bundlePath, buildConfig.PublishBinDirectorySubPath);

                // Copy binaries
                FileUtility.CopyDirectory(buildConfig.PublishBinDirectoryPath, targetBundleBinariesPath);

                string extensionJsonFilePath = Path.Join(targetBundleBinariesPath, Settings.ExtensionsJsonFileName);
                AddBindingInfoToExtensionsJson(extensionJsonFilePath);
            }

            // Copy templates
            var staticContentDirectory = Path.Combine(bundlePath, Settings.StaticContentDirectoryName);
            FileUtility.CopyDirectory(Settings.StaticContentDirectoryPath, staticContentDirectory);

            // Add bundle.json
            CreateBundleJsonFile(bundlePath);

            // Add Csproj file
            string projectPath = Path.Combine(bundlePath, "extensions.csproj");
            File.Copy(bundlePackageConfig.CsProjFilePath, projectPath);

            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            ZipFile.CreateFromDirectory(bundlePath, bundlePackageConfig.GeneratedBundleZipFilePath, CompressionLevel.NoCompression, false);
        }


        public static void GenerateNetCoreV2Bundle()
        {
            CreateExtensionBundle(Settings.BundlePackageNetCoreV2Any);
        }


        public static void GenerateNetCoreV3BundlesLinux()
        {
            CreateExtensionBundle(Settings.BundlePackageNetCoreV3Any);
            CreateExtensionBundle(Settings.BundlePackageNetCoreV3Linux);
        }

        public static void GenerateNetCoreV3BundlesWindows()
        {
            CreateExtensionBundle(Settings.BundlePackageNetCoreV3Any);
            CreateExtensionBundle(Settings.BundlePackageNetCoreWindows);
        }

        public static void AddBundleZipFile(string rootPath, BundlePackageConfiguration packageConfig)
        {
            string bundleZipDestinationPath = Path.Combine(rootPath, packageConfig.GeneratedBundleZipFileName);
            FileUtility.CopyFile(packageConfig.GeneratedBundleZipFilePath, bundleZipDestinationPath);
        }

        public static void CreateRUPackage()
        {
            FileUtility.EnsureDirectoryExists(Settings.RUPackagePath);

            ZipFile.ExtractToDirectory(Settings.BundlePackageNetCoreWindows.GeneratedBundleZipFilePath, Settings.RUPackagePath);

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

                AddBundleZipFile(bundleVersionDirectory, Settings.BundlePackageNetCoreV2Any);

                // Add bundle.json
                CreateBundleJsonFile(bundleVersionDirectory);

                // Add Csproj file
                string projectPath = Path.Combine(bundleVersionDirectory, "extensions.csproj");
                File.Copy(Settings.BundlePackageNetCoreV2Any.CsProjFilePath, projectPath);

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
                string packageBundleDirectory = Path.Combine(packageRootDirectoryPath, Settings.ExtensionBundleId, Settings.ExtensionBundleBuildVersion);
                FileUtility.EnsureDirectoryExists(packageBundleDirectory);

                AddBundleZipFile(packageBundleDirectory, Settings.BundlePackageNetCoreV3Linux);

                string packageZipFilePath = Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}_linux.zip");
                ZipFile.CreateFromDirectory(packageRootDirectoryPath, packageZipFilePath, CompressionLevel.NoCompression, false);
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
