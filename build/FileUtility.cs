using System;
using System.IO;
using System.IO.Abstractions;
using System.Text;

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

        public static void EnsureDirectoryExists(string path)
        {
            if (!Instance.Directory.Exists(path))
            {
                Instance.Directory.CreateDirectory(path);
            }
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

        public static string ReadAllText(string path) => Instance.File.ReadAllText(path);

        public static Stream OpenFile(string path, FileMode mode, FileAccess access = FileAccess.ReadWrite, FileShare share = FileShare.None)
        {
            return Instance.File.Open(path, mode, access, share);
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
    }
}