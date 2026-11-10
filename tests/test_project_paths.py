import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import project_paths


class ProjectPathsTests(unittest.TestCase):
    def test_explicit_dataset_path_overrides_environment(self):
        with patch.dict(os.environ, {'ATTENTION_DATA_DIR':'/tmp/other-data'}):
            self.assertEqual(project_paths.data_directory('/tmp/my-data'),Path('/tmp/my-data').resolve())

    def test_environment_dataset_path(self):
        with patch.dict(os.environ, {'ATTENTION_DATA_DIR':'/tmp/attention-data'}):
            self.assertEqual(project_paths.data_directory(),Path('/tmp/attention-data').resolve())

    def test_bundled_result_when_generated_output_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(project_paths,'ROOT',root),patch.object(project_paths,'RESULTS',root/'examples/results'):
                self.assertEqual(project_paths.result_file('outputs/results.csv','snapshot.csv'),root/'examples/results/snapshot.csv')
                generated=root/'outputs/results.csv';generated.parent.mkdir();generated.write_text('header\n')
                self.assertEqual(project_paths.result_file('outputs/results.csv','snapshot.csv'),generated)
