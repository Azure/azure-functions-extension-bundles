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
        public static void CleanOutputDirectory()
        {
            if (FileUtility.DirectoryExists(Settings.OutputDir))
            {
                Directory.Delete(Settings.OutputDir, recursive: true);
            }
        }

        public static void CreateOutputDirectory()
        {
            FileUtility.EnsureDirectoryExists(Settings.OutputDir);
        }

        public static void CopyProjectToOutputDirectory()
        {
            FileUtility.CopyFile(Settings.ProjectFile, Settings.OutputProjectFile);
        }

        public static void BuildExtensionsProject()
        {
            var feeds = Settings.nugetFeed.Aggregate(string.Empty, (a, b) => $"{a} --source {b}");
            Shell.Run("dotnet", $"build {Settings.OutputProjectFile} -o {Settings.OutputBinDir}");
        }

        public static void AddPackages()
        {
            var extensions = GetExtensionList();
            foreach (var extension in extensions)
            {
                //                ColoredConsole.Out.WriteLine($"installing extension {extension.Id}:{extension.Version}");
                Shell.Run("dotnet", $"add {Settings.OutputProjectFile} package {extension.Id} -v {extension.Version} -n");
            }
        }

        private static List<Extensions> GetExtensionList()
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText(Settings.ExtensionsJsonFile);
            return JsonConvert.DeserializeObject<List<Extensions>>(extensionsJsonFileContent);
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

        //public static async Task UploadZip()
        //{
        //    var storageConnection = Settings.SignInfo.AzureSigningConnectionString;
        //    var storageAccount = CloudStorageAccount.Parse(storageConnection);
        //    var blobClient = storageAccount.CreateCloudBlobClient();
        //    var blobContainer = blobClient.GetContainerReference(Settings.SignInfo.AzureToSignContainerName);
        //    await blobContainer.CreateIfNotExistsAsync();
        //    foreach (var supportedRuntime in Settings.SignInfo.RuntimesToSign)
        //    {
        //        var targetDir = Path.Combine(Settings.OutputDir, supportedRuntime);

        //        var toSignBlob = blobContainer.GetBlockBlobReference($"{Settings.SignInfo.ToSignZipName}-{supportedRuntime}");
        //        await toSignBlob.UploadFromFileAsync(Path.Combine(targetDir, Settings.SignInfo.ToSignDir, Settings.SignInfo.ToSignZipName));

        //        var toSignThirdPartyBlob = blobContainer.GetBlockBlobReference($"{Settings.SignInfo.ToSignThirdPartyName}-{supportedRuntime}");
        //        await toSignThirdPartyBlob.UploadFromFileAsync(Path.Combine(targetDir, Settings.SignInfo.ToSignDir, Settings.SignInfo.ToSignThirdPartyName));
        //    }
        //}

        //public static void UploadToStorage()
        //{
        //    if (!string.IsNullOrEmpty(Settings.BuildArtifactsStorage))
        //    {
        //        var version = new Version(CurrentVersion);
        //        var storageAccount = CloudStorageAccount.Parse(Settings.BuildArtifactsStorage);
        //        var blobClient = storageAccount.CreateCloudBlobClient();
        //        var container = blobClient.GetContainerReference("builds");
        //        container.CreateIfNotExistsAsync().Wait();

        //        container.SetPermissionsAsync(new BlobContainerPermissions
        //        {
        //            PublicAccess = BlobContainerPublicAccessType.Blob
        //        });

        //        foreach (var file in Directory.GetFiles(Settings.OutputDir, "Azure.Functions.Cli.*", SearchOption.TopDirectoryOnly))
        //        {
        //            var fileName = Path.GetFileName(file);
        //            ColoredConsole.Write($"Uploading {fileName}...");

        //            var versionedBlob = container.GetBlockBlobReference($"{version.ToString()}/{fileName}");
        //            var latestBlob = container.GetBlockBlobReference($"{version.Major}/latest/{fileName.Replace($".{version.ToString()}", string.Empty)}");
        //            versionedBlob.UploadFromFileAsync(file).Wait();
        //            latestBlob.StartCopyAsync(versionedBlob).Wait();

        //            ColoredConsole.WriteLine("Done");
        //        }

        //        var latestVersionBlob = container.GetBlockBlobReference($"{version.Major}/latest/version.txt");
        //        latestVersionBlob.UploadTextAsync(version.ToString()).Wait();
        //    }
        //    else
        //    {
        //        var error = $"{nameof(Settings.BuildArtifactsStorage)} is null or empty. Can't run {nameof(UploadToStorage)} target";
        //        ColoredConsole.Error.WriteLine(error.Red());
        //        throw new Exception(error);
        //    }
        //}

        //public static void Zip()
        //{
        //    var version = CurrentVersion;
        //    foreach (var runtime in Settings.TargetRuntimes)
        //    {
        //        var path = Path.Combine(Settings.OutputDir, runtime);

        //        var zipPath = Path.Combine(Settings.OutputDir, $"Azure.Functions.Cli.{runtime}.{version}.zip");
        //        ColoredConsole.WriteLine($"Creating {zipPath}");
        //        ZipFile.CreateFromDirectory(path, zipPath, CompressionLevel.Optimal, includeBaseDirectory: false);

        //        var shaPath = $"{zipPath}.sha2";
        //        ColoredConsole.WriteLine($"Creating {shaPath}");
        //        File.WriteAllText(shaPath, ComputeSha256(zipPath));

        //        try
        //        {
        //            Directory.Delete(path, recursive: true);
        //        }
        //        catch
        //        {
        //            ColoredConsole.Error.WriteLine($"Error deleting {path}");
        //        }

        //        ColoredConsole.WriteLine();
        //    }

        //    string ComputeSha256(string file)
        //    {
        //        using (var fileStream = File.OpenRead(file))
        //        {
        //            var sha1 = new SHA256Managed();
        //            return BitConverter.ToString(sha1.ComputeHash(fileStream)).Replace("-", string.Empty);
        //        }
        //    }
        //}
    }
}