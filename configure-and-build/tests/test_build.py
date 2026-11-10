import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "build.py"
SPEC = importlib.util.spec_from_file_location("opencv_ci_build", SCRIPT)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BuildArgumentsTests(unittest.TestCase):
    def test_default_preserves_platform_build_arguments(self):
        for system, suffix in (("Windows", ["--config", "Release"]), ("Linux", []), ("macOS", [])):
            with self.subTest(system=system):
                self.assertEqual(
                    build.build_arguments("a build directory", system, "Ninja"),
                    ["--build", "a build directory"] + suffix,
                )

    def test_shared_budget_is_applied_to_projects_and_compiler_workers(self):
        self.assertEqual(
            build.build_arguments("build", "Windows", "Visual Studio 17 2022", "true", "8"),
            [
                "--build", "build", "--config", "Release", "--parallel", "8", "--",
                "/p:MultiProcCL=true", "/p:MultiProcMaxCount=8",
                "/p:EnforceProcessCountAcrossBuilds=true", "/nr:false",
            ],
        )

    def test_unsupported_or_ambiguous_settings_fail(self):
        cases = [
            ("Linux", "Visual Studio 17 2022", "true", "8"),
            ("Windows", "Ninja", "true", "8"),
            ("Windows", "", "true", "8"),
            ("Windows", "Visual Studio 17 2022", "false", "8"),
            ("Windows", "Visual Studio 17 2022", "yes", ""),
        ]
        cases += [
            ("Windows", "Visual Studio 17 2022", "true", value)
            for value in ("", "0", "-1", "1.5", "8 /p:Other=true")
        ]
        for case in cases:
            with self.subTest(settings=case), self.assertRaises(ValueError):
                build.build_arguments("build", *case)

    def test_shared_budget_requires_the_actual_configured_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "CMakeCache.txt"
            for content in ("CMAKE_GENERATOR:INTERNAL=Ninja\n", "OTHER:STRING=value\n"):
                cache.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ValueError):
                    build.check_generator(directory, "Visual Studio 17 2022")
            cache.write_text("CMAKE_GENERATOR:INTERNAL=Visual Studio 17 2022\n", encoding="utf-8")
            build.check_generator(directory, "Visual Studio 17 2022")

    def test_validation_does_not_start_a_build_or_require_a_build_tree(self):
        with mock.patch.object(build, "run_build") as run:
            self.assertEqual(build.main([
                "--builddir", "not-configured", "--runner-os", "Windows",
                "--generator", "Visual Studio 17 2022",
                "--shared-cap", "true", "--compiler-jobs", "8", "--validate-only",
            ]), 0)
            run.assert_not_called()

    def test_invalid_cli_settings_report_an_error_without_building(self):
        with mock.patch.object(build, "run_build") as run, contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(build.main([
                "--builddir", "not-configured", "--shared-cap", "true",
                "--generator", "Ninja", "--compiler-jobs", "8",
            ]), 2)
            self.assertIn("::error::", errors.getvalue())
            run.assert_not_called()


class BuildProcessTests(unittest.TestCase):
    def test_build_does_not_inherit_interactive_input(self):
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "build log.txt"
            code = (
                "import importlib.util,sys;"
                "s=importlib.util.spec_from_file_location('b',sys.argv[1]);"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "sys.exit(m.run_build([sys.executable,'-c',"
                "\"import sys;print(len(sys.stdin.read()))\"],sys.argv[2]))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code, str(SCRIPT), str(logfile)],
                input=b"must not reach the build", stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), b"0")
            self.assertEqual(logfile.read_bytes(), result.stdout)

    def test_output_is_teed_and_native_failure_is_propagated(self):
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "build log.txt"
            code = (
                "import importlib.util,sys;"
                "s=importlib.util.spec_from_file_location('b',sys.argv[1]);"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "sys.exit(m.run_build([sys.executable,'-c',"
                "\"import sys;print('build output');print('build error',file=sys.stderr);sys.exit(7)\"],"
                "sys.argv[2]))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code, str(SCRIPT), str(logfile)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(logfile.read_bytes(), result.stdout)
            self.assertIn(b"build output", result.stdout)
            self.assertIn(b"build error", result.stdout)


if __name__ == "__main__":
    unittest.main()
