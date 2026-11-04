"""The homepage must request new digest bytes after a new deployment."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import build

NOW = datetime(2026, 11, 4, 9, tzinfo=timezone.utc)


class DataAssetCacheTests(unittest.TestCase):
    def make_root(self, directory):
        root = Path(directory)
        for folder in ('config', 'data', 'site'):
            (root / folder).mkdir()
        (root / 'config/sources.json').write_text('{"sources": []}')
        (root / 'data/discoveries.json').write_text('{"items": []}')
        (root / 'site/index.html').write_text('<script src="data.js" defer></script><script src="app.js" defer></script>')
        return root

    def data_filename(self, root):
        html = (root / 'public/index.html').read_text()
        match = re.search(r'src="(data\.[a-f0-9]{20}\.js)"', html)
        self.assertIsNotNone(match)
        self.assertNotIn('src="data.js"', html)
        self.assertIn('src="app.js" defer', html)
        return match.group(1)

    def test_html_uses_existing_relative_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            build(root, 'https://example.com/repo/', NOW)
            filename = self.data_filename(root)
            script = (root / 'public' / filename).read_bytes()
            self.assertEqual(filename, 'data.' + hashlib.sha256(script).hexdigest()[:20] + '.js')
            self.assertEqual(script, (root / 'public/data.js').read_bytes())
            self.assertIn(b'window.TECH_DATA = ', script)

    def test_changed_data_gets_new_url_without_changing_source_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            source_html = (root / 'site/index.html').read_text()
            build(root, '', NOW)
            first = self.data_filename(root)
            (root / 'data/discoveries.json').write_text(json.dumps({'items': [{
                'id': 'sample', 'title': 'A new discovery', 'url': 'https://example.com/',
                'category': 'software', 'verified_at': '2026-11-04', 'added_at': '2026-11-04'
            }]}))
            build(root, '', NOW)
            self.assertNotEqual(first, self.data_filename(root))
            self.assertEqual(source_html, (root / 'site/index.html').read_text())

    def test_same_payload_keeps_same_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            build(root, '', NOW)
            first = self.data_filename(root)
            build(root, '', NOW)
            self.assertEqual(first, self.data_filename(root))


if __name__ == '__main__':
    unittest.main()
