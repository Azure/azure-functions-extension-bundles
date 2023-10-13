// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License. See License.txt in the project root for license information.

using Xunit;

namespace Microsoft.Azure.Functions.ExtensionBundle.Tests
{
    public class DependencyValidationTests
    {
        public DependencyValidationTests()
        {}

        [Fact]
        public void Test_Success()
        {
            Assert.True(1 == 1);
        }

        [Fact]
        public void Test_Fails()
        {
            Assert.False(1 == 1);
        }
    }
}