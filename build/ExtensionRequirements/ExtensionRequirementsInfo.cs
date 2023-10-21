// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License. See License.txt in the project root for license information.

using System;
using System.Collections.Generic;
using System.Linq;

namespace Build
{
    internal sealed class ExtensionRequirementsInfo
    {
        public ExtensionRequirementsInfo(IEnumerable<BundleRequirement> bundleRequirements, IEnumerable<ExtensionStartupTypeRequirement> extensionRequirements)
        {
            BundleRequirementsByBundleId = bundleRequirements
                .ToDictionary(a => a.Id, StringComparer.OrdinalIgnoreCase);

            ExtensionRequirementsByStartupType = extensionRequirements
                .ToDictionary(a => a.Name, StringComparer.OrdinalIgnoreCase);
        }

        public Dictionary<string, BundleRequirement> BundleRequirementsByBundleId { get; private set; }

        public Dictionary<string, ExtensionStartupTypeRequirement> ExtensionRequirementsByStartupType { get; private set; }
    }
}
