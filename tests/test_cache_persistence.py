"""Exercise cache-save failure handling without accessing a remote repository."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/save_feed_cache.sh'
MOCK_GIT = '''#!/bin/sh
printf '%s\\n' "$*" >> "$GIT_CALLS"
case "$1" in
  diff) exit "$CACHE_DIFF_EXIT" ;;
  push) printf '%s\\n' "$PUSH_MESSAGE"; exit "$PUSH_EXIT" ;;
  *) exit 0 ;;
esac
'''


class CachePersistenceTests(unittest.TestCase):
    def run_save(self, message='', push_exit=0, changed=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = root / 'git'
            git.write_text(MOCK_GIT)
            git.chmod(0o755)
            calls = root / 'calls.txt'
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'GIT_CALLS': str(calls), 'CACHE_DIFF_EXIT': '1' if changed else '0',
                   'PUSH_MESSAGE': message, 'PUSH_EXIT': str(push_exit)}
            result = subprocess.run(['bash', str(SCRIPT)], env=env, cwd=root,
                                    text=True, capture_output=True)
            return result, calls.read_text().splitlines()

    def test_server_failure_warns_and_allows_validated_deployment(self):
        result, calls = self.run_save('remote: Internal Server Error', 1)
        self.assertEqual(result.returncode, 0)
        self.assertIn('::warning::', result.stdout)
        self.assertIn('save was not confirmed', result.stdout)
        self.assertEqual(calls[-1], 'push')
        self.assertIn('add data/news.json data/source_status.json', calls)
        self.assertFalse(any('--force' in call or 'reset' in call for call in calls))

    def test_authorization_failure_remains_blocking(self):
        result, _ = self.run_save('remote: Permission denied. HTTP 403', 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('::warning::', result.stdout)

    def test_success_needs_no_warning(self):
        result, calls = self.run_save('main -> main')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('::warning::', result.stdout)
        self.assertEqual(calls[-1], 'push')

    def test_branch_conflict_remains_blocking(self):
        result, calls = self.run_save('! [rejected] main -> main (non-fast-forward)', 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('::warning::', result.stdout)
        self.assertEqual(calls[-1], 'push')

    def test_unchanged_cache_does_not_commit_or_push(self):
        result, calls = self.run_save(changed=False)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(any(call.startswith(('commit', 'push')) for call in calls))


if __name__ == '__main__':
    unittest.main()
