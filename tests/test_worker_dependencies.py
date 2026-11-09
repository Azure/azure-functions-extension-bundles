# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Regression tests for the dependency isolation setting passed to Core Tools."""

import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from tests.utils import testutils


class TestWorkerDependencies(unittest.TestCase):
    def test_isolation_is_unset_by_default(self):
        environment = self._start_host({})
        self.assertNotIn('PYTHON_ISOLATE_WORKER_DEPENDENCIES', environment)

    def test_explicit_isolation_settings_are_preserved(self):
        for value in ('0', '1', 'true', 'false', ''):
            with self.subTest(value=value):
                environment = self._start_host({
                    'PYTHON_ISOLATE_WORKER_DEPENDENCIES': value,
                })
                self.assertEqual(
                    environment['PYTHON_ISOLATE_WORKER_DEPENDENCIES'], value)

    def _start_host(self, settings):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            executable = root / 'func'
            executable.touch()
            environment = {
                'CORE_TOOLS_EXE_PATH': str(executable),
                **settings,
            }
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(testutils, 'WORKER_CONFIG', root / 'worker.config.ini'),
                patch.object(testutils.subprocess, 'Popen') as popen,
            ):
                process = testutils.popen_webhost(
                    stdout=None, stderr=None, script_root=root, port=7071)
                self.assertIs(process, popen.return_value)
                popen.assert_called_once()
                host_environment = popen.call_args.kwargs['env']
                self.assertEqual(host_environment['FUNCTIONS_WORKER_RUNTIME'], 'python')
                config = (root / 'webhost_config.txt').read_text()
                self.assertEqual(
                    'PYTHON_ISOLATE_WORKER_DEPENDENCIES' in config,
                    'PYTHON_ISOLATE_WORKER_DEPENDENCIES' in settings)
                return host_environment


if __name__ == '__main__':
    unittest.main()
