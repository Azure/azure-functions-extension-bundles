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
            if (FileUtility.DirectoryExists(Settings.OutputDirectory))
            {
                Directory.Delete(Settings.OutputDirectory, recursive: true);
            }

            if (FileUtility.DirectoryExists(Settings.ArtifactsDirectory))
            {
                Directory.Delete(Settings.ArtifactsDirectory, recursive: true);
            }
        }

        public static void CreateOutputDirectory()
        {
            FileUtility.EnsureDirectoryExists(Settings.OutputDirectory);
        }

        public static void CopyProjectToOutputDirectory()
        {
            FileUtility.CopyFile(Settings.ProjectFile, Settings.OutputProjectFile);
        }

        public static void BuildExtensionsProject()
        {
            var feeds = Settings.nugetFeed.Aggregate(string.Empty, (a, b) => $"{a} --source {b}");
            Shell.Run("dotnet", $"publish {Settings.OutputProjectFile} -c Release -o {Settings.OutputBinTempDirectory}");
            var binariesPath = Path.Combine(Settings.OutputBinTempDirectory, "bin");
            FileUtility.DeleteDirectory(Settings.OutputBinDirectory, true);
            FileUtility.CopyDirectory(binariesPath, Settings.OutputBinDirectory);
            FileUtility.DeleteDirectory(Settings.OutputBinTempDirectory, true);
        }

        public static void AddPackages()
        {
            var extensions = GetExtensionList();
            foreach (var extension in extensions)
            {
                Shell.Run("dotnet", $"add {Settings.OutputProjectFile} package {extension.Id} -v {extension.Version} -n");
            }
        }

        private static List<Extension> GetExtensionList()
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText(Settings.ExtensionsJsonFile);
            return JsonConvert.DeserializeObject<List<Extension>>(extensionsJsonFileContent);
        }

        public static void DownloadTemplates()
        {
            string zipDirectoryPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            FileUtility.EnsureDirectoryExists(zipDirectoryPath);
            string templatesZipUri = $"https://functionscdn.azureedge.net/public/ExtensionBundleTemplates/ExtensionBundle.v2.Templates.{Settings.TemplatesVersion}.zip";
            string zipFilePath = Path.Combine(zipDirectoryPath, $"templates.zip");
            var zipUri = new Uri(templatesZipUri);

            if (DownloadZipFile(zipUri, zipFilePath))
            {
                FileUtility.EnsureDirectoryExists(Settings.OutputTemplatesDirectory);
                ZipFile.ExtractToDirectory(zipFilePath, Settings.OutputTemplatesDirectory);
            }
            if (!FileUtility.DirectoryExists(Settings.OutputTemplatesDirectory) || !FileUtility.FileExists(Settings.OutputTemplatesJsonFile))
            {
                throw new Exception("Template download failed");
            }

            if (FileUtility.DirectoryExists(Settings.OutputTemplatesDirectory) || FileUtility.FileExists(Settings.ResourcesFile))
            {
                FileUtility.CopyFile(Settings.ResourcesFile, Settings.ResourcesEnUSFile);
            }


            if (!FileUtility.DirectoryExists(Settings.OutputTemplatesDirectory) || !FileUtility.FileExists(Settings.ResourcesEnUSFile))
            {
                throw new Exception("Resource Copy failed");
            }
        }

        public static void AddBindingInfoToExtensionsJson()
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText(Settings.OutputExtensionJsonFile);
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
            FileUtility.Write(Settings.OutputExtensionJsonFile, JsonConvert.SerializeObject(outputExtensions));
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

        public static void CreateBundleZipFile()
        {
            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            ZipFile.CreateFromDirectory(Settings.OutputDirectory, Path.Combine(Settings.ArtifactsDirectory, $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}.zip"), CompressionLevel.NoCompression, false);
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
                string directoryPath = Path.Combine(Settings.OutputDirectory, indexFileMetadata.IndexFileDirectory, Settings.ExtensionBundleId);
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

                var indexFilePath = Path.Combine(Settings.OutputDirectory, indexFileMetadata.IndexFileDirectory, Settings.ExtensionBundleId, Settings.IndexFileName);
                FileUtility.Write(indexFilePath, JsonConvert.SerializeObject(indexFile));
                ZipFile.CreateFromDirectory(Path.Combine(Settings.OutputDirectory, indexFileMetadata.IndexFileDirectory), Path.Combine(Settings.ArtifactsDirectory, $"{indexFileMetadata.IndexFileDirectory}.zip"), CompressionLevel.NoCompression, false);
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

        public static void CreateBundleJsonFile()
        {
            var serializer = new JsonSerializerSettings();
            serializer.NullValueHandling = NullValueHandling.Ignore;
            Extension bundleInfo = new Extension()
            {
                Id = Settings.ExtensionBundleId,
                Version = Settings.ExtensionBundleBuildVersion
            };
            var fileContents = JsonConvert.SerializeObject(bundleInfo, serializer);

            FileUtility.Write(Settings.OutputBundleJsonFile, fileContents);
        }

        public static void RemoveObjFolderFromOutPutDirectory()
        {
            FileUtility.DeleteDirectory(Path.Combine(Settings.OutputDirectory, "obj"), true);
        }
    }
}
