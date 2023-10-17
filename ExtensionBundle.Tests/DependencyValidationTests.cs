﻿// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License. See License.txt in the project root for license information.

using Build;
using Newtonsoft.Json;
using System.Collections.Generic;
using System.Linq;
using Xunit;

namespace Microsoft.Azure.Functions.ExtensionBundle.Tests
{
    public class DependencyValidationTests
    {
        internal List<Extension> extensionsList;
        internal Dictionary<string, int> testExtensionsDict;

        public DependencyValidationTests()
        {
            var extensionsJsonFileContent = FileUtility.ReadAllText("../../../../src/Microsoft.Azure.Functions.ExtensionBundle/extensions.json");
            extensionsList = JsonConvert.DeserializeObject<List<Extension>>(extensionsJsonFileContent);

            var testExtensionsJsonFileContent = FileUtility.ReadAllText("../../../TestData/TestExtensions.json");
            var testExtensionsList = JsonConvert.DeserializeObject<List<Extension>>(testExtensionsJsonFileContent);
            testExtensionsDict = testExtensionsList.ToDictionary(ext => ext.Id, ext => ext.MajorVersion);
        }

        [Fact]
        public void Test_Version_Mismatch()
        {
            foreach (var extension in extensionsList)
            {
                if (testExtensionsDict.ContainsKey(extension.Id))
                {
                    if (testExtensionsDict[extension.Id] != extension.MajorVersion)
                    {
                        Assert.Fail("Changing major version is not allowed and will be considered as breaking change.");
                    }
                }
            }
        }
    }
}