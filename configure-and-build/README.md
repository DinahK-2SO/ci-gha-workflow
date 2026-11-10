# Configuring and building OpenCV

The action's default native CMake build arguments are unchanged. Windows uses
`--config Release`; other platforms retain the configured build type.
`CMAKE_BUILD_PARALLEL_LEVEL` remains effective when no explicit budget is passed.
With the option disabled, the action retains its direct CMake/tee build path;
the Python build helper is used only for the enabled Windows option.

## Optional shared MSBuild compiler budget

Set `msbuild_shared_cap: 'true'` together with a positive decimal
`msbuild_compiler_jobs` value to select MultiToolTask compilation, project
parallelism, a shared compiler-process cap and disabled worker-node reuse.
Both inputs default to the original behavior. Supplying a budget without
enabling the option is rejected rather than ignored.

The option requires Windows and a Visual Studio generator. The build helper
also checks the configured generator before running a shared-cap build. Do not
use this option for Ninja or non-Windows jobs. The cap counts compiler
processes, not all threads, linker processes or total machine CPU usage.

The reusable Windows workflow exposes an opt-in `msbuild_shared_cap` input.
When enabled, it is routed only to the 5.x ARM64/VS2022 row and uses the existing
`CMAKE_BUILD_PARALLEL_LEVEL` value. Other rows retain the original behavior.
This is not a guarantee of improved build time or energy use; target workload
and hardware validation is required before broadening adoption.

## Local invocation of the same build helper

After separately configuring a build tree and selecting the intended CMake on
PATH, the same committed helper can be called without GitHub Actions:

```text
python configure-and-build/build.py --builddir <configured-build-directory>
python configure-and-build/build.py --builddir <configured-build-directory> --generator "Visual Studio 17 2022" --shared-cap true --compiler-jobs 8
```

The example budget is not a universal optimum. The helper does not clone,
configure, clean, install tools, change system settings or dispatch jobs.
It preserves CMake output in `<builddir>/log.txt`, streams it to the caller
and returns the native build exit code. The build receives noninteractive stdin,
including when launched by a service with no valid inherited input handle.
Validate arguments without starting a
build by adding `--validate-only`.

Record source and workflow repository commits, effective configuration and
machine conditions separately when comparing builds. Download/configure/clean
time is not build-only time, and an uncommitted local edit is not evidence for
a published commit. Keep logs for each independent attempt.

Focused checks use only the Python standard library:

```text
python -m unittest discover -s configure-and-build/tests -v
```
