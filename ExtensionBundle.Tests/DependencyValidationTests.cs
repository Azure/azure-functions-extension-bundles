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

        [InlineData("any_any_extensions.deps.json", "any_any")]
        [InlineData("win_x86_extensions.deps.json", "x86")]
        [InlineData("win_x64_extensions.deps.json", "x64")]
        [Theory]
        public void Verify_DepsJsonChanges(string oldDepsJsonName, string newDepsJsonName)
        {
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                return;
            }

            string oldDepsJson = Path.GetFullPath($"../../../TestData/{oldDepsJsonName}");
            string webhostBinPath = Path.Combine("..", "..", "..", "..", "build_temp");
            string newDepsJson = Directory.GetFiles(Path.GetFullPath(webhostBinPath), "extensions.deps.json", SearchOption.AllDirectories)
                                            .Where(path => path.Contains(newDepsJsonName))
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
            var assemblyToIgnore = "extensions.dll";

            var removed = oldAssets.Except(newAssets, comparer).ToList();
            removed = removed.Where(f => !(f.Path.Contains(assemblyToIgnore) && f.AssemblyVersion == null)).ToList();

            var added = newAssets.Except(oldAssets, comparer).ToList();
            added = added.Where(f => !(f.Path.Contains(assemblyToIgnore) && f.AssemblyVersion == null)).ToList();

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
                    return Path.GetFileName(p.Path) == fileName
                        && Version.TryParse(p.AssemblyVersion, out Version newVersion)
                        && Version.TryParse(oldFile.AssemblyVersion, out Version oldVersion)
                        && newVersion.Major != oldVersion.Major;
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
                return Version.TryParse(x.AssemblyVersion, out Version xVersion)
                    && Version.TryParse(y.AssemblyVersion, out Version yVersion)
                    && xVersion.Major == yVersion.Major;
            }

            public int GetHashCode([DisallowNull] RuntimeFile obj)
            {
                Version.TryParse(obj.AssemblyVersion, out Version objVersion);
                if (objVersion != null)
                {
                    string code = objVersion.Major.ToString();
                    return code.GetHashCode();
                }

                return 0;
            }
        }
    }
}