import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice-loop"))
from czech_assets import ensure_assets, verified


class CzechAssets(unittest.TestCase):
    def test_checks_content_and_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'fixture.onnx')
            path.write_bytes(b'example model')
            expected = hashlib.sha256(b'example model').hexdigest()
            self.assertTrue(verified(path,13,'sha256',expected))
            path.write_bytes(b'changed model')
            self.assertFalse(verified(path,13,'sha256',expected))

    def test_git_blob_verification_for_small_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder,'config.json')
            path.write_bytes(b'{}')
            expected = hashlib.sha1(b'blob 2\0{}').hexdigest()
            self.assertTrue(verified(path,2,'git',expected))

    def test_missing_model_fails_closed_in_offline_mode(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch('czech_assets.ROOT',Path(folder)), \
                mock.patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(RuntimeError,'missing or invalid'):
                ensure_assets('piper',download=False)
            network.assert_not_called()
