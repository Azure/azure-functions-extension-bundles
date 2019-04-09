using Colors.Net;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;

namespace Build
{
    public static class BuildSteps
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
            Shell.Run("dotnet", $"build {Settings.OutputProjectFile} -o {Settings.OutputBinDirectory}");
        }

        public static void AddPackages()
        {
            var extensions = GetExtensionList();
            foreach (var extension in extensions)
            {
                Shell.Run("dotnet", $"add {Settings.OutputProjectFile} package {extension.Id} -v {extension.Version} -n");
            }
        }

        private static List<ExtensionBundleInfo> GetExtensionList()
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText(Settings.ExtensionsJsonFile);
            return JsonConvert.DeserializeObject<List<ExtensionBundleInfo>>(extensionsJsonFileContent);
        }

        public static void DownloadTemplates()
        {
            string zipDirectoryPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            FileUtility.EnsureDirectoryExists(zipDirectoryPath);

            string zipFilePath = Path.Combine(zipDirectoryPath, $"templates.zip");
            var zipUri = new Uri(Settings.TemplatesZipUri);

            if (DownloadZipFile(zipUri, zipFilePath))
            {
                FileUtility.EnsureDirectoryExists(Settings.OutputTemplatesDirectory);
                ZipFile.ExtractToDirectory(zipFilePath, Settings.OutputTemplatesDirectory);
            }
            if (!FileUtility.DirectoryExists(Settings.OutputTemplatesDirectory) || !FileUtility.FileExists(Settings.OutputTemplatesJsonFile))
            {
                throw new Exception("Template download failed");
            }
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

        public static void ZipOutputDirectory()
        {
            FileUtility.EnsureDirectoryExists(Settings.ArtifactsDirectory);
            ZipFile.CreateFromDirectory(Settings.OutputDirectory, Path.Combine(Settings.ArtifactsDirectory, $"{Settings.ExtensionBundleId}.{Settings.ExtensionBundleBuildVersion}.zip"), CompressionLevel.NoCompression, false);
        }

        public static void CreateBundleJsonFile()
        {
            ExtensionBundleInfo bundleInfo = new ExtensionBundleInfo()
            {
                Id = Settings.ExtensionBundleId,
                Version = Settings.ExtensionBundleBuildVersion
            };
            var fileContents = JsonConvert.SerializeObject(bundleInfo);

            FileUtility.Write(Settings.OutputBundleJsonFile, fileContents);
        }

        public static void RemoveObjFolderFromOutPutDirectory()
        {
            FileUtility.DeleteDirectory(Path.Combine(Settings.OutputDirectory, "obj"), true);
        }
    }
}