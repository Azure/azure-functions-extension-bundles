// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License. See License.txt in the project root for license information.

using Build;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Microsoft.Extensions.DependencyModel;
using Xunit;
using System.Diagnostics.CodeAnalysis;
using System.Runtime.InteropServices;

namespace Microsoft.Azure.Functions.ExtensionBundle.Tests
{
    [Collection("Fixture")]
    public class DependencyValidationTests
    {
        private readonly DependencyContextJsonReader _reader = new DependencyContextJsonReader();
        private readonly IEnumerable<string> _rids = DependencyHelper.GetRuntimeFallbacks();
        private readonly Fixture _fixture;

        public DependencyValidationTests(Fixture fixture)
        {
            _fixture = fixture;
        }

        [Fact]
        public void Verify_DepsJsonChanges_Windows_Any()
        {            
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                return;
            }

            string oldDepsJson = Path.GetFullPath("../../../TestData/win_any_extensions.deps.json");
            string webhostBinPath = Path.Combine("..", "..", "..", "..", "build_temp");
            string newDepsJson = Directory.GetFiles(Path.GetFullPath(webhostBinPath), "extensions.deps.json", SearchOption.AllDirectories)
                                            .Where(path => path.Contains("win_x64"))
                                            .FirstOrDefault();

            Assert.True(File.Exists(oldDepsJson), $"{oldDepsJson} not found.");
            Assert.True(File.Exists(newDepsJson), $"{newDepsJson} not found.");

            (bool succeed, string output) = CompareDepsJsonFiles(oldDepsJson, newDepsJson);

            if (succeed == true)
            {
                return;
            }

            Assert.True(succeed, output);
        }

        [Fact]
        public void Verify_DepsJsonChanges_Any_Any()
        {
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                return;
            }

            string oldDepsJson = Path.GetFullPath("../../../TestData/any_any_extensions.deps.json");
            string webhostBinPath = Path.Combine("..", "..", "..", "..", "build_temp");
            string newDepsJson = Directory.GetFiles(Path.GetFullPath(webhostBinPath), "extensions.deps.json", SearchOption.AllDirectories)
                                            .Where(path => path.Contains("NetCoreApp3_any_any"))
                                            .FirstOrDefault();

            Assert.True(File.Exists(oldDepsJson), $"{oldDepsJson} not found.");
            Assert.True(File.Exists(newDepsJson), $"{newDepsJson} not found.");

            (bool succeed, string output) = CompareDepsJsonFiles(oldDepsJson, newDepsJson);

            if (succeed == true)
            {
                return;
            }

            Assert.True(succeed, output);
        }

        [Fact]
        public void Verify_DepsJsonChanges_Linux_X64()
        {
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                return;
            }

            string oldDepsJson = Path.GetFullPath("../../../TestData/linux_x64_extensions.deps.json");
            string webhostBinPath = Path.Combine("..", "..", "..", "..", "build_temp");
            string newDepsJson = Directory.GetFiles(Path.GetFullPath(webhostBinPath), "extensions.deps.json", SearchOption.AllDirectories)
                                            .Where(path => path.Contains("x64"))
                                            .FirstOrDefault();

            Assert.True(File.Exists(oldDepsJson), $"{oldDepsJson} not found.");
            Assert.True(File.Exists(newDepsJson), $"{newDepsJson} not found.");

            (bool succeed, string output) = CompareDepsJsonFiles(oldDepsJson, newDepsJson);

            if (succeed == true)
            {
                return;
            }

            Assert.True(succeed, output);
        }


        private (bool, string) CompareDepsJsonFiles(string oldDepsJson, string newDepsJson)
        {

            IEnumerable<RuntimeFile> oldAssets = GetRuntimeFiles(oldDepsJson);
            IEnumerable<RuntimeFile> newAssets = GetRuntimeFiles(newDepsJson);

            var comparer = new RuntimeFileComparer();

            var removed = oldAssets.Except(newAssets, comparer).ToList();
            var added = newAssets.Except(oldAssets, comparer).ToList();

            bool succeed = removed.Count == 0 && added.Count == 0;

            if (succeed)
            {
                return (succeed, null);
            }

            IList<RuntimeFile> changed = new List<RuntimeFile>();
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("IMPORTANT: The dependencies in extensions have changed and MUST be reviewed before proceeding. Please follow up with brettsam, fabiocav, nasoni or mathewc for approval.");
            sb.AppendLine();
            sb.AppendLine($"Previous file: {oldDepsJson}");
            sb.AppendLine($"New file:      {newDepsJson}");
            sb.AppendLine();
            sb.AppendLine("  Changed:");
            foreach (RuntimeFile oldFile in oldAssets)
            {
                string fileName = Path.GetFileName(oldFile.Path);

                var newFile = newAssets.SingleOrDefault(p =>
                {
                    return Path.GetFileName(p.Path) == fileName &&
                        (p.FileVersion != oldFile.FileVersion ||
                         p.AssemblyVersion != oldFile.AssemblyVersion);
                });

                if (newFile != null)
                {
                    sb.AppendLine($"    - {fileName}: {oldFile.AssemblyVersion}/{oldFile.FileVersion} -> {newFile.AssemblyVersion}/{newFile.FileVersion}");
                    changed.Add(oldFile);
                    changed.Add(newFile);
                }
            }

            sb.AppendLine();
            sb.AppendLine("  Removed:");
            foreach (RuntimeFile f in removed.Except(changed))
            {
                sb.AppendLine($"    - {Path.GetFileName(f.Path)}: {f.AssemblyVersion}/{f.FileVersion}");
            }
            sb.AppendLine();
            sb.AppendLine("  Added:");
            foreach (RuntimeFile f in added.Except(changed))
            {
                sb.AppendLine($"    - {Path.GetFileName(f.Path)}: {f.AssemblyVersion}/{f.FileVersion}");
            }

            return (succeed, sb.ToString());
        }

        private IEnumerable<RuntimeFile> GetRuntimeFiles(string depsJsonFileName)
        {
            using (Stream s = new FileStream(depsJsonFileName, FileMode.Open))
            {
                DependencyContext deps = _reader.Read(s);

                return deps.RuntimeLibraries
                    .SelectMany(l => SelectRuntimeAssemblyGroup(_rids, l.RuntimeAssemblyGroups))
                    .OrderBy(p => Path.GetFileName(p.Path));
            }
        }

        private static IEnumerable<RuntimeFile> SelectRuntimeAssemblyGroup(IEnumerable<string> rids, IReadOnlyList<RuntimeAssetGroup> runtimeAssemblyGroups)
        {
            // Attempt to load group for the current RID graph
            foreach (var rid in rids)
            {
                var assemblyGroup = runtimeAssemblyGroups.FirstOrDefault(g => string.Equals(g.Runtime, rid, StringComparison.OrdinalIgnoreCase));
                if (assemblyGroup != null)
                {
                    return assemblyGroup.RuntimeFiles;
                }
            }

            // If unsuccessful, load default assets, making sure the path is flattened to reflect deployed files
            return runtimeAssemblyGroups.GetDefaultRuntimeFileAssets();
        }


        private class RuntimeFileComparer : IEqualityComparer<RuntimeFile>
        {
            public bool Equals([AllowNull] RuntimeFile x, [AllowNull] RuntimeFile y)
            {
                return x.AssemblyVersion == y.AssemblyVersion &&
                    x.FileVersion == y.FileVersion &&
                    x.Path == y.Path;
            }

            public int GetHashCode([DisallowNull] RuntimeFile obj)
            {
                string code = obj.Path + obj.AssemblyVersion + obj.FileVersion;
                return code.GetHashCode();
            }
        }
    }
}