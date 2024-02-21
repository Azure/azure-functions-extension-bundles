using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Abstractions;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;

namespace Build
{
    public static class FileUtility
    {
        private static IFileSystem _default = new FileSystem();
        private static IFileSystem _instance;

        public static IFileSystem Instance
        {
            get { return _instance ?? _default; }
            set { _instance = value; }
        }

        public static void RecursiveCopy(string sourcePath, string destinationPath)
        {
            // Get the subdirectories for the specified directory.
            var dir = new DirectoryInfo(sourcePath);

            if (!dir.Exists)
            {
                throw new DirectoryNotFoundException(
                    "Source directory does not exist or could not be found: "
                    + sourcePath);
            }

            var dirs = dir.GetDirectories();
            // If the destination directory doesn't exist, create it.
            if (!Directory.Exists(destinationPath))
            {
                Directory.CreateDirectory(destinationPath);
            }

            // Get the files in the directory and copy them to the new location.
            var files = dir.GetFiles();
            foreach (var file in files)
            {
                var temppath = Path.Combine(destinationPath, file.Name);
                file.CopyTo(temppath, false);
            }

            // If copying subdirectories, copy them and their contents to new location.
            foreach (var subdir in dirs)
            {
                var temppath = Path.Combine(destinationPath, subdir.Name);
                RecursiveCopy(subdir.FullName, temppath);
            }
        }

        public static void ExtractZipFileForce(string zipFile, string to)
        {
            using (var archive = ZipFile.OpenRead(zipFile))
            {
                foreach (ZipArchiveEntry file in archive.Entries)
                {
                    file.ExtractToFile(Path.Combine(to, file.FullName), overwrite: true);
                }
            }
        }

        public static void CreateZipFile(IEnumerable<string> files, string baseDir, string zipFilePath)
        {
            using (var zipfile = ZipFile.Open(zipFilePath, ZipArchiveMode.Create))
            {
                foreach (var file in files)
                {
                    zipfile.CreateEntryFromFile(file, Path.GetRelativePath(baseDir, file), CompressionLevel.NoCompression);
                }
            }
        }

        public static string ReadResourceString(string resourcePath, Assembly assembly = null)
        {
            assembly = assembly ?? Assembly.GetCallingAssembly();
            using (StreamReader reader = new StreamReader(assembly.GetManifestResourceStream(resourcePath)))
            {
                return reader.ReadToEnd();
            }
        }

        public static void EnsureDirectoryExists(string path)
        {
            if (!Instance.Directory.Exists(path))
            {
                Instance.Directory.CreateDirectory(path);
            }
        }

        public static Task DeleteDirectoryAsync(string path, bool recursive)
        {
            return Task.Run(() =>
            {
                if (Instance.Directory.Exists(path))
                {
                    Instance.Directory.Delete(path, recursive);
                }
            });
        }

        public static void DeleteDirectory(string path, bool recursive)
        {
            if (Instance.Directory.Exists(path))
            {
                Instance.Directory.Delete(path, recursive);
                System.Threading.Thread.Sleep(1000);
            }

        }

        public static Task<bool> DeleteIfExistsAsync(string path)
        {
            return Task.Run(() =>
            {
                if (Instance.File.Exists(path))
                {
                    Instance.File.Delete(path);
                    return true;
                }
                return false;
            });
        }

        public static void Write(string path, string contents, Encoding encoding = null)
        {
            if (path == null)
            {
                throw new ArgumentNullException(nameof(path));
            }

            if (contents == null)
            {
                throw new ArgumentNullException(nameof(contents));
            }

            Encoding utf8WithoutBom = new UTF8Encoding(false);
            encoding = encoding ?? utf8WithoutBom;

            EnsureDirectoryExists(Path.GetDirectoryName(path));
            Stream fileStream = OpenFile(path, FileMode.Create, FileAccess.Write, FileShare.Read);
            var writer = new StreamWriter(fileStream, encoding, 4096);
            writer.Write(contents);
            writer.Close();
            fileStream.Close();
        }

        public static async Task<string> ReadAsync(string path, Encoding encoding = null)
        {
            if (path == null)
            {
                throw new ArgumentNullException(nameof(path));
            }

            encoding = encoding ?? Encoding.UTF8;
            using (var fileStream = OpenFile(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            using (var reader = new StreamReader(fileStream, encoding, true, 4096))
            {
                return await reader.ReadToEndAsync();
            }
        }

        public static string ReadAllText(string path) => Instance.File.ReadAllText(path);

        public static Stream OpenFile(string path, FileMode mode, FileAccess access = FileAccess.ReadWrite, FileShare share = FileShare.None)
        {
            return Instance.File.Open(path, mode, access, share);
        }

        public static string GetRelativePath(string path1, string path2)
        {
            if (path1 == null)
            {
                throw new ArgumentNullException(nameof(path1));
            }

            if (path2 == null)
            {
                throw new ArgumentNullException(nameof(path2));
            }

            string EnsureTrailingSeparator(string path)
            {
                if (!Path.HasExtension(path) && !path.EndsWith(Path.DirectorySeparatorChar.ToString()))
                {
                    path = path + Path.DirectorySeparatorChar;
                }

                return path;
            }

            path1 = EnsureTrailingSeparator(path1);
            path2 = EnsureTrailingSeparator(path2);

            var uri1 = new Uri(path1);
            var uri2 = new Uri(path2);

            Uri relativeUri = uri1.MakeRelativeUri(uri2);
            string relativePath = Uri.UnescapeDataString(relativeUri.ToString())
                .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);

            return relativePath;
        }

        public static Task<string[]> GetFilesAsync(string path, string prefix)
        {
            if (path == null)
            {
                throw new ArgumentNullException(nameof(path));
            }

            if (prefix == null)
            {
                throw new ArgumentNullException(nameof(prefix));
            }

            return Task.Run(() =>
            {
                return Instance.Directory.GetFiles(path, prefix);
            });
        }

        public static string[] GetFiles(string path)
        {
            if (path == null)
            {
                throw new ArgumentNullException(nameof(path));
            }

            return Instance.Directory.GetFiles(path);
        }

        public static void CopyFile(string sourcePath, string targetPath)
        {
            File.Copy(sourcePath, targetPath, true);
        }

        public static void CopyDirectory(string sourcePath, string targetPath)
        {
            if (!Directory.Exists(targetPath))
            {
                Directory.CreateDirectory(targetPath);
            }

            foreach (string dirPath in Instance.Directory.GetDirectories(sourcePath, "*", SearchOption.AllDirectories))
            {
                Instance.Directory.CreateDirectory(dirPath.Replace(sourcePath, targetPath));
            }

            foreach (string filePath in Instance.Directory.GetFiles(sourcePath, "*.*", SearchOption.AllDirectories))
            {
                Instance.File.Copy(filePath, filePath.Replace(sourcePath, targetPath), true);
            }
        }

        public static bool FileExists(string path) => Instance.File.Exists(path);

        public static bool DirectoryExists(string path) => Instance.Directory.Exists(path);

        public static DirectoryInfoBase DirectoryInfoFromDirectoryName(string localSiteRootPath) => Instance.DirectoryInfo.FromDirectoryName(localSiteRootPath);

        public static FileInfoBase FileInfoFromFileName(string localFilePath) => Instance.FileInfo.FromFileName(localFilePath);

        public static string GetFullPath(string path) => Instance.Path.GetFullPath(path);

        private static void DeleteDirectoryContentsSafe(DirectoryInfoBase directoryInfo, bool ignoreErrors)
        {
            try
            {
                if (directoryInfo.Exists)
                {
                    foreach (var fsi in directoryInfo.GetFileSystemInfos())
                    {
                        DeleteFileSystemInfo(fsi, ignoreErrors);
                    }
                }
            }
            catch when (ignoreErrors)
            {
            }
        }

        private static void DeleteFileSystemInfo(FileSystemInfoBase fileSystemInfo, bool ignoreErrors)
        {
            if (!fileSystemInfo.Exists)
            {
                return;
            }

            try
            {
                fileSystemInfo.Attributes = FileAttributes.Normal;
            }
            catch when (ignoreErrors)
            {
            }

            if (fileSystemInfo is DirectoryInfoBase directoryInfo)
            {
                DeleteDirectoryContentsSafe(directoryInfo, ignoreErrors);
            }

            DoSafeAction(fileSystemInfo.Delete, ignoreErrors);
        }

        public static void DeleteDirectoryContentsSafe(string path, bool ignoreErrors = true)
        {
            try
            {
                var directoryInfo = DirectoryInfoFromDirectoryName(path);
                if (directoryInfo.Exists)
                {
                    foreach (var fsi in directoryInfo.GetFileSystemInfos())
                    {
                        DeleteFileSystemInfo(fsi, ignoreErrors);
                    }
                }
            }
            catch when (ignoreErrors)
            {
            }
        }

        public static void DeleteFileSafe(string path)
        {
            try
            {
                var info = FileInfoFromFileName(path);
                DeleteFileSystemInfo(info, ignoreErrors: true);
            }
            catch
            {
            }
        }

        public static IEnumerable<string> EnumerateDirectories(string path) => Instance.Directory.EnumerateDirectories(path);

        private static void DoSafeAction(Action action, bool ignoreErrors)
        {
            try
            {
                action();
            }
            catch when (ignoreErrors)
            {
            }
        }
    }
}