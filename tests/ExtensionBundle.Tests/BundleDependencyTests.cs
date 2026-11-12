// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License. See License.txt in the project root for license information.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using Xunit;

namespace Microsoft.Azure.Functions.ExtensionBundle.Tests
{
    [Collection("Fixture")]
    public class BundleDependencyTests
    {
        public static IEnumerable<object[]> BuildConfigurations()
        {
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                yield return new object[] { "linux_x64", "linux-x64" };
            }
            else
            {
                yield return new object[] { "any_any", null };
                yield return new object[] { "win_any_any", null };
                yield return new object[] { "win_x86", "win-x86" };
                yield return new object[] { "win_x64", "win-x64" };
            }
        }

        [Theory]
        [MemberData(nameof(BuildConfigurations))]
        public void Verify_WebUtilitiesAndRemovedDependencies(string configuration, string runtimeIdentifier)
        {
            string root = Path.GetFullPath(Path.Combine("..", "..", "..", "..", ".."));
            string assetsPath = Path.Combine(root, "build_temp", configuration, "obj", "project.assets.json");
            using JsonDocument assets = JsonDocument.Parse(File.ReadAllText(assetsPath));
            string[] libraries = assets.RootElement.GetProperty("libraries")
                .EnumerateObject()
                .Select(library => library.Name)
                .ToArray();

            const string webUtilitiesPrefix = "Microsoft.AspNetCore.WebUtilities/";
            string webUtilities = Assert.Single(libraries, library =>
                library.StartsWith(webUtilitiesPrefix, StringComparison.OrdinalIgnoreCase));
            string versionText = webUtilities.Substring(webUtilitiesPrefix.Length);
            Assert.True(
                Version.TryParse(versionText, out Version version) &&
                version.Major == 2 &&
                version >= new Version(2, 3, 14),
                $"{configuration} resolved an unpatched WebUtilities version: {versionText}");

            JsonElement directDependencies = assets.RootElement.GetProperty("project")
                .GetProperty("frameworks").GetProperty("net8.0").GetProperty("dependencies");
            Assert.True(directDependencies.TryGetProperty("Microsoft.AspNetCore.WebUtilities", out _));
            Assert.False(directDependencies.TryGetProperty("Microsoft.AspNetCore.Server.Kestrel.Core", out _));
            Assert.DoesNotContain(libraries, library =>
                library.StartsWith("Microsoft.Azure.WebJobs.Extensions.Dapr/", StringComparison.OrdinalIgnoreCase) ||
                library.StartsWith("Microsoft.Azure.Functions.Extensions.Dapr.Core/", StringComparison.OrdinalIgnoreCase));

            string publishedBin = runtimeIdentifier == null
                ? Path.Combine(root, "bin", configuration, "bin")
                : Path.Combine(root, "bin", configuration, "bin_v3", runtimeIdentifier);
            using JsonDocument publishedDeps = JsonDocument.Parse(File.ReadAllText(Path.Combine(publishedBin, "function.deps.json")));
            Assert.True(publishedDeps.RootElement.GetProperty("libraries").TryGetProperty(webUtilities, out _));
            string runtimeTarget = publishedDeps.RootElement.GetProperty("runtimeTarget").GetProperty("name").GetString();
            JsonElement publishedWebUtilities = publishedDeps.RootElement.GetProperty("targets").GetProperty(runtimeTarget).GetProperty(webUtilities);
            Assert.False(publishedWebUtilities.TryGetProperty("runtime", out _));
            Assert.False(publishedWebUtilities.TryGetProperty("runtimeTargets", out _));
            Assert.Empty(Directory.EnumerateFiles(publishedBin, "Microsoft.AspNetCore.WebUtilities.dll", SearchOption.AllDirectories));
        }
    }
}
