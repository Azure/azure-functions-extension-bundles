---
name: extension-bundle-dependency-review
description: Run extension-bundle unit tests, investigate dependency baseline failures against adjacent Azure DevOps scheduled builds, assess shared and host runtime risks, and update approved dependency baselines. Use when bundle dependency validation tests fail, an assembly major version changes, or someone asks to review or accept a deps bump.
---

# Extension bundle dependency review

Use this skill only in the `Azure/azure-functions-extension-bundles` repository.

## Inputs

- Use the branch supplied by the user.
- If no branch is supplied, use the current Git branch when it has an upstream Azure DevOps build history. Otherwise, ask which branch to inspect.
- The public Azure DevOps pipeline is definition `939`:
  `https://dev.azure.com/azfunc/public/_build?definitionId=939`
- The internal Azure DevOps pipeline used for Linux release artifacts is definition `922`:
  `https://dev.azure.com/azfunc/internal/_build?definitionId=922`
- If the user supplies build IDs, use them after verifying that they are scheduled builds for the selected branch.

## Safety rules

- Do not update dependency baselines merely to make tests pass.
- Establish the extension responsible for the bump, all extension consumers of the assembly, and Azure Functions host resolution behavior first.
- A single-extension dependency that is not shared with the host can normally be accepted when the responsible extension has already validated the upgrade.
- If multiple extensions consume the dependency and the major upgrade can break compatibility, stop before editing. Report the affected extensions and the coordination/testing required.
- If the host carries or overrides the assembly at another major version, stop before editing unless compatibility with the host resolution policy is established.
- Preserve unrelated worktree changes. Do not commit unless explicitly requested.
- Do not claim a transitive dependency path without evidence from a deps file, assets file, NuGet metadata, or package contents.

## Workflow

### 0. Prepare a working branch

Create a dedicated working branch from the branch being investigated before editing baselines. Fetch the remote
first. If the requested working branch already exists remotely, switch to its tracking branch and pull it with
fast-forward only instead of recreating it. Preserve unrelated worktree changes and do not include them in the
dependency-review commit.

### 1. Run the same unit tests as CI

Resolve every `**/*Tests.csproj` under the repository. Run each with:

```powershell
dotnet test <project> --configuration Release --no-restore
```

If the failure is caused by missing restored assets, run the repository's existing restore command from
`eng/ci/templates/jobs/run-unit-test.yml`, then rerun the test. Do not restore automatically for other failures.

Capture every dependency-validation change, including:

- baseline and generated deps file paths
- assembly name
- old and new assembly versions
- old and new file versions
- affected runtime configurations

If tests pass, report that no dependency review or baseline update is needed and stop.
If failures are unrelated to dependency validation, report them and stop this workflow.

### 2. Select the build transition

Query Azure DevOps for scheduled builds of definition `939` on the exact branch ref
(`refs/heads/<branch>`). The public REST API is:

```text
https://dev.azure.com/azfunc/public/_apis/build/builds
  ?definitions=939
  &branchName=refs/heads/<branch>
  &reasonFilter=schedule
  &queryOrder=queueTimeDescending
  &api-version=7.1
```

Follow continuation tokens if the first page does not contain the transition. Sort the returned runs
chronologically and select the most recent adjacent transition where:

1. the earlier scheduled build completed successfully, and
2. the immediately following scheduled build failed.

Do not compare a non-adjacent success and failure, because that can combine several extension updates.
Record both build IDs, timestamps, source commits, results, and links. If no adjacent transition exists,
stop and report that the build pair could not be established.

### 3. Download and compare `any_any` artifacts

For both builds, enumerate artifacts with:

```text
https://dev.azure.com/azfunc/public/_apis/build/builds/<buildId>/artifacts?api-version=7.1
```

Download `bundle_artifact`. If that exact name is absent, inspect the artifact list and select the artifact
that actually contains the `any_any` bundle; report the observed artifact name rather than silently assuming
one. Extract both builds into a temporary directory outside the repository and remove it when finished.

Within each artifact:

1. locate the `any_any` bundle content;
2. locate and compare its generated `.csproj` files;
3. compare `PackageReference` IDs and resolved versions structurally, not only as raw text;
4. identify which extension NuGet changed between the builds; and
5. verify that the new extension package was published between the two build timestamps using package metadata.

Read `NuGet.config` and use its configured package source for registration and package metadata. Do not call
`api.nuget.org` directly; it may be blocked in the development environment. Resolve the feed's
`RegistrationsBaseUrl/3.6.0` resource from its NuGet v3 service index, then query the lower-cased package ID's
registration document for the version and `published` timestamp.

If multiple extension packages changed, use the failing assembly's dependency graph to identify the responsible
package rather than guessing from timestamps.

### 4. Trace the failing library to extension consumers

Open the failing build artifact's `functions.deps.json`. If the artifact uses a differently named generated
deps file, use the equivalent file containing the full bundle dependency graph and report its actual path.

Use the `targets` and `libraries` sections to:

1. find packages whose runtime assets contain the failing assembly;
2. walk dependency edges backward through transitive packages; and
3. identify every top-level extension package that reaches that assembly.

Report each complete evidence-backed chain using this shape:

```text
top-level extension
  -> transitive package
  -> package containing or depending on the assembly
  -> failing assembly
```

Treat two extensions as consumers even if they reach the assembly through different transitive paths.

### 5. Assess cross-extension breaking-change risk

If more than one extension consumes the assembly:

1. read official release notes, changelogs, and migration guidance for the library versions spanning the major bump;
2. identify binary, API, serialization, or behavioral breaking changes relevant to the discovered paths;
3. determine whether all consuming extensions support the same loaded major version; and
4. require coordinated validation when compatibility is not clearly established.

Prefer first-party project and NuGet sources. Include links and distinguish documented facts from inference.

### 6. Check Azure Functions host resolution

Inspect the current `dev` version of:

```text
https://github.com/Azure/azure-functions-host/blob/dev/src/WebJobs.Script/runtimeassemblies.json
```

Search case-insensitively for the failing assembly. When present:

1. record the host assembly version and `resolutionPolicy`;
2. find the implementation/specification for that policy in `Azure/azure-functions-host`;
3. explain whether the host unifies, overrides, rejects, or otherwise constrains the extension assembly; and
4. compare the policy's accepted version range with the extension's new major version.

Also inspect directly related host runtime-assembly manifests when the referenced policy requires them.
Absence from `runtimeassemblies.json` must be reported explicitly; do not infer host sharing solely from absence.

### 7. Decide and update baselines

The bump is acceptable only when the evidence supports all applicable conditions:

- the responsible extension/package is identified;
- the extension release timing matches the successful-to-failing build transition;
- every extension consumer is identified;
- shared consumers are compatible or have coordinated testing;
- host resolution does not create a conflicting major-version load; and
- the responsible extension has validated the dependency change.

For an acceptable bump, copy each locally generated `extensions.deps.json` over only its corresponding baseline:

| Runtime configuration | Baseline |
| --- | --- |
| `any_any` | `tests/ExtensionBundle.Tests/TestData/any_any_extensions.deps.json` |
| `win_x64` | `tests/ExtensionBundle.Tests/TestData/win_x64_extensions.deps.json` |
| `win_x86` | `tests/ExtensionBundle.Tests/TestData/win_x86_extensions.deps.json` |
| `linux_x64` | `tests/ExtensionBundle.Tests/TestData/linux_x64_extensions.deps.json` |

Update only configurations reported by the test unless the generated files prove the same reviewed change applies
to another tracked configuration.

On Windows, obtain the Linux baseline from internal pipeline definition `922`:

1. filter runs to the exact concerned branch;
2. select the latest failed run whose `Build` stage succeeded;
3. enumerate that run's artifacts and use the `zip` artifact;
4. download only `/Microsoft.Azure.Functions.ExtensionBundle.<version>_linux-x64.zip` from the artifact rather
   than downloading the complete multi-gigabyte artifact;
5. extract `bin_v3/linux-x64/function.deps.json`;
6. confirm it contains the same reviewed dependency bump; and
7. copy it to `tests/ExtensionBundle.Tests/TestData/linux_x64_extensions.deps.json`.

The pipeline artifact single-file REST request uses its `resource.downloadUrl` with `format=file` and a
URL-encoded, leading-slash `subPath`. Authenticate internal Azure DevOps requests without printing access tokens.

Rerun the CI-equivalent test command after editing.

### 8. Commit and open the pull request

When the user requests a commit and pull request:

1. stage only the reviewed dependency baselines and this skill when it changed;
2. commit on the dedicated working branch;
3. include the repository-required commit trailers;
4. push the branch without force;
5. read and preserve `.github/pull_request_template.md`;
6. open the PR against the investigated base branch; and
7. fill the template with brief evidence-based justification from this review: the build transition, responsible
   extension release, dependency chain and consumer count, host resolution result, updated configurations, and
   final test result.

Do not leave template placeholders or claim unrelated test coverage.

## Required result

Lead with one decision: `safe to update`, `coordination required`, `host conflict risk`, or `inconclusive`.
Then provide:

- local test summary and exact assembly bump
- selected successful/failing build pair
- changed extension NuGet and publication evidence
- complete dependency chain(s) and all consumers
- breaking-change assessment when shared
- host manifest/policy result
- baseline files changed, if any
- final test result

Include source URLs and file paths. State missing evidence plainly and never convert an inconclusive review into an
automatic baseline update.
