---
name: extension-bundle-dependency-review
description: Run extension-bundle unit and emulator tests, investigate dependency baseline failures against Azure DevOps builds, assess shared and host runtime risks, and update approved dependency baselines. Use when bundle dependency validation or emulator tests fail, an assembly major version changes, or someone asks to review, accept, or pin a dependency bump.
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
- A build used to establish an automatic dependency transition must be a scheduled build for the selected branch.
- A user-supplied manual build may be used to diagnose or retest that exact branch and commit. Record its reason instead of rejecting it for not being scheduled.

## Safety rules

- Do not update dependency baselines merely to make tests pass.
- Establish the extension responsible for the bump, all extension consumers of the assembly, and Azure Functions host resolution behavior first.
- A single-extension dependency that is not shared with the host can normally be accepted when the responsible extension has already validated the upgrade.
- If multiple extensions consume the dependency and the major upgrade can break compatibility, stop before editing. Report the affected extensions and the coordination/testing required.
- If the host carries or overrides the assembly at another major version, stop before editing unless compatibility with the host resolution policy is established.
- Do not treat a host source change as available until the pipeline's Core Tools or host artifact contains it.
- Preserve unrelated worktree changes. Do not commit unless explicitly requested.
- Do not claim a transitive dependency path without evidence from a deps file, assets file, NuGet metadata, or package contents.
- Do not classify a type-resolution error as independent when a missing assembly appears in the type's signature or generated state machine. Establish the causal relationship first.
- Do not assume a newer dependency requires a newer .NET SDK. Check the selected target-framework assets and build errors.

## Workflow

### 0. Prepare a working branch

Create a dedicated working branch from the branch being investigated before editing baselines. Fetch the remote
first. If the requested working branch already exists remotely, switch to its tracking branch and pull it with
fast-forward only instead of recreating it. Preserve unrelated worktree changes and do not include them in the
dependency-review commit.
If the working branch already contains prior dependency-review edits, ask the user whether to reset, amend, or
continue before proceeding.

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

If Azure DevOps queries fail due to authentication, network errors, or rate limiting, report the exact error and
stop; do not proceed with baseline updates using local evidence alone.

Follow continuation tokens if the first page does not contain the transition. Sort the returned runs
chronologically and select the most recent adjacent transition where:

1. the earlier scheduled build completed successfully, and
2. the immediately following scheduled build failed.

Do not compare a non-adjacent success and failure, because that can combine several extension updates.
Record both build IDs, timestamps, source commits, results, and links. If no adjacent transition exists,
report that the build pair could not be established. A user-requested branch build can still be analyzed as
diagnostic evidence, but it does not establish package publication timing.

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

Read `NuGet.config` and honor both `<packageSources>` and `<packageSourceMapping>` when selecting the source for
the package. Do not call `api.nuget.org` directly; it may be blocked in the development environment.

From the selected source's NuGet v3 service index:

1. resolve its `RegistrationsBaseUrl/3.6.0` resource;
2. query `<registration-base>/<lower-case-package-id>/index.json`;
3. select the exact version's catalog entry and record its `published`, dependency groups, and `packageContent`;
4. use the catalog entry's `packageContent` URL to download the `.nupkg` when package inspection is needed; or
5. resolve `PackageBaseAddress/3.0.0` and download
   `<package-base>/<lower-case-id>/<lower-case-version>/<lower-case-id>.<lower-case-version>.nupkg`.

Use `dotnet restore --configfile NuGet.config` when restoring a project so package source mapping and configured
credentials are applied consistently. Public feeds require no added credentials. For authenticated feeds, use
the environment's existing Azure Artifacts credential provider or access token without printing or persisting
the credential. Never add a source, token, or credential to the repository.

If multiple extension packages changed, use the failing assembly's dependency graph to identify every responsible
package rather than guessing from timestamps or attributing a shared dependency to the first changed extension.

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

Treat two extensions as consumers even if they reach the assembly through different transitive paths. Remember
that the bundle has one shared dependency graph: an incompatible assembly selected by one upgraded extension can
break unchanged extensions at startup.

### 5. Diagnose emulator failures

For a branch or validation build, inspect the failed stage, job, and task logs rather than relying only on the
overall result. Separate expected dependency-baseline failures from emulator/runtime failures.

For emulator failures:

1. inventory passing and failing emulator suites to identify a shared startup failure;
2. compare the generated `function.deps.json` dependency and runtime entries with DLLs physically present in the bundle;
3. record the requested assembly version, the packaged version or absence, and the host-provided version;
4. trace secondary type-load failures through method signatures, generated async state machines, package assets,
   and source diffs before declaring a separate extension regression; and
5. verify the project TFM and selected NuGet asset TFM before recommending an SDK upgrade.

If a proposed host fix changes assembly resolution, wait until that host commit is present in the Core Tools or
host artifact used by the emulator pipeline, then rerun the emulator tests. A merged host PR alone is insufficient
validation.

### 6. Assess cross-extension breaking-change risk

If more than one extension consumes the assembly:

1. read official release notes, changelogs, and migration guidance for the library versions spanning the major bump;
2. identify binary, API, serialization, or behavioral breaking changes relevant to the discovered paths;
3. determine whether all consuming extensions support the same loaded major version; and
4. require coordinated validation when compatibility is not clearly established.

Prefer first-party project and NuGet sources. Include links and distinguish documented facts from inference.

### 7. Check Azure Functions host resolution

Inspect the current `dev` version of:

```text
https://github.com/Azure/azure-functions-host/blob/dev/src/WebJobs.Script/runtimeassemblies.json
```

Search case-insensitively for the failing assembly. When present:

1. record the host package and assembly versions and `resolutionPolicy`;
2. find the implementation and tests for that policy in `Azure/azure-functions-host`;
3. explain whether the host unifies, overrides, rejects, or otherwise constrains the extension assembly;
4. compare the policy's accepted version range with the extension's new major version; and
5. inspect pending host changes when relevant, but distinguish source-branch compatibility from the host version
   actually used by the emulator build.

Also inspect directly related host runtime-assembly manifests when the referenced policy requires them.
Absence from `runtimeassemblies.json` must be reported explicitly; do not infer host sharing solely from absence.

### 8. Decide whether to accept or pin

Apply the first matching decision in this table:

| Condition | Decision |
| --- | --- |
| Host policy conflicts with the new assembly major, or a required host-side change is absent from the host artifact used by emulator tests | `host conflict risk` |
| Multiple extensions consume the assembly and compatibility across all consumers is not established | `coordination required` |
| The responsible package, complete consumer set, or responsible extension's validation is missing | `inconclusive` |
| An automatic dependency-transition review lacks matching publication timing from an adjacent scheduled build pair | `inconclusive` |
| Host compatibility, consumer compatibility, responsible package, release evidence when required, and extension validation are all established | `safe to update` |

If pinning is requested, verify the pin changes the resolved shared graph as intended. Pinning one extension may
not remove the conflicting assembly when another extension independently requires the same major version.

### 9. Update baselines

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
3. confirm the run's source commit and generated extension versions match the change under review;
4. enumerate that run's artifacts and use the `zip` artifact;
5. download only `/Microsoft.Azure.Functions.ExtensionBundle.<version>_linux-x64.zip` from the artifact rather
   than downloading the complete multi-gigabyte artifact;
6. extract `bin_v3/linux-x64/function.deps.json`;
7. confirm it contains the complete reviewed dependency graph, not merely one of several requested bumps; and
8. copy it to `tests/ExtensionBundle.Tests/TestData/linux_x64_extensions.deps.json`.

The pipeline artifact single-file REST request uses its `resource.downloadUrl` with `format=file` and a
URL-encoded, leading-slash `subPath`. Authenticate internal Azure DevOps requests without printing access tokens.

Rerun the CI-equivalent test command after editing.

### 10. Commit and open the pull request

When the user requests a commit and pull request:

1. stage only the reviewed dependency baselines and this skill when it changed;
2. commit on the dedicated working branch;
3. push the branch without force;
4. read and preserve `.github/pull_request_template.md`;
5. open the PR against the investigated base branch; and
6. fill the template with brief evidence-based justification from this review: the build transition, responsible
   extension release, dependency chain and consumer count, emulator result, host resolution result, updated
   configurations, and final test result.

Do not leave template placeholders or claim unrelated test coverage. When queueing Azure DevOps against a specific
commit, pass the full 40-character source SHA.

## Required result

Lead with one decision: `safe to update`, `coordination required`, `host conflict risk`, or `inconclusive`.
Then provide:

- local test summary and exact assembly bump
- selected successful/failing build pair, or why no scheduled pair was available
- changed extension NuGet and publication evidence
- complete dependency chain(s) and all consumers
- emulator test diagnosis, when applicable
- breaking-change assessment when shared
- host manifest/policy result and the host version actually tested
- baseline or pin files changed, if any
- final test result

Include source URLs and file paths. State missing evidence plainly and never convert an inconclusive review into an
automatic baseline update.
