import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def build_arguments(builddir, runner_os, generator, shared_cap="false", compiler_jobs=""):
    if shared_cap not in ("false", "true"):
        raise ValueError("msbuild_shared_cap must be 'false' or 'true'")
    if shared_cap == "false" and compiler_jobs:
        raise ValueError("msbuild_compiler_jobs requires msbuild_shared_cap=true")
    if shared_cap == "true":
        if runner_os != "Windows":
            raise ValueError("Shared MSBuild scheduling requires Windows")
        if not re.fullmatch(r"Visual Studio \d+ \d{4}", generator):
            raise ValueError("Shared MSBuild scheduling requires a Visual Studio generator")
        if not re.fullmatch(r"[1-9][0-9]*", compiler_jobs):
            raise ValueError("msbuild_compiler_jobs must be a positive decimal integer")

    arguments = ["--build", builddir]
    if runner_os == "Windows":
        arguments += ["--config", "Release"]
    if shared_cap == "true":
        arguments += [
            "--parallel", compiler_jobs,
            "--",
            "/p:MultiProcCL=true",
            "/p:MultiProcMaxCount=" + compiler_jobs,
            "/p:EnforceProcessCountAcrossBuilds=true",
            "/nr:false",
        ]
    return arguments


def check_generator(builddir, expected):
    cache = Path(builddir) / "CMakeCache.txt"
    for line in cache.read_text(encoding="utf-8").splitlines():
        if line.startswith("CMAKE_GENERATOR:INTERNAL="):
            actual = line.partition("=")[2]
            if actual != expected:
                raise ValueError("Configured generator {!r} differs from {!r}".format(actual, expected))
            return
    raise ValueError("CMAKE_GENERATOR is missing from " + str(cache))


def run_build(command, log_path):
    with open(log_path, "wb") as log:
        with subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        ) as process:
            for chunk in iter(lambda: process.stdout.read1(65536), b""):
                log.write(chunk)
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            return process.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a configured OpenCV tree without changing its inputs")
    parser.add_argument("--builddir", required=True)
    parser.add_argument("--runner-os", default="Windows" if os.name == "nt" else "Linux")
    parser.add_argument("--generator", default="")
    parser.add_argument("--shared-cap", default="false")
    parser.add_argument("--compiler-jobs", default="")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        arguments = build_arguments(
            args.builddir, args.runner_os, args.generator, args.shared_cap, args.compiler_jobs
        )
        if args.validate_only:
            return 0
        if args.shared_cap == "true":
            check_generator(args.builddir, args.generator)
        cmake = shutil.which("cmake")
        if cmake is None:
            raise ValueError("cmake was not found on PATH")
        return run_build([cmake] + arguments, Path(args.builddir) / "log.txt")
    except (OSError, ValueError) as error:
        print("::error::" + str(error), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
