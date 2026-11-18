import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent.parent / 'skills/project-knowledge/scripts' / 'merge.py'


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.vault = self.repo / 'vault'
        (self.vault / '.knowledge').mkdir(parents=True)
        self.note('old.md', 'old', 'base')
        self.note('shared.md', 'shared', 'base')
        (self.vault / '.knowledge/review.json').write_text('base')
        self.commit('base')
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-b', 'ours')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, text=True, check=True).stdout

    def note(self, name, ident, body=''):
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\nid: ' + json.dumps(ident) + '\n---\n' + body + '\n')

    def commit(self, msg):
        self.git('add', '-A')
        self.git('commit', '-m', msg)

    def call(self, ours='ours', theirs='theirs', repo=None, vault=None):
        return subprocess.run(['python3', str(SCRIPT), 'inspect', '--repo', str(repo or self.repo), '--vault', str(vault or self.vault), '--ours', ours, '--theirs', theirs, '--json'], capture_output=True, text=True)

    def test_overlap_rename_delete_duplicate_and_states_without_mutation(self):
        self.git('mv', 'vault/old.md', 'vault/renamed.md')
        self.note('shared.md', 'shared', 'ours')
        self.note('a.md', 'same-id', 'ours')
        self.note('both.md', 'ours-id', 'ours')
        (self.vault / '.knowledge/review.json').write_text('ours')
        self.commit('ours')
        self.git('checkout', '-b', 'theirs', self.base)
        self.git('rm', 'vault/old.md')
        self.note('shared.md', 'shared', 'theirs')
        self.note('b.md', 'same-id', 'theirs')
        self.note('both.md', 'theirs-id', 'theirs')
        (self.vault / '.knowledge/review.json').write_text('theirs')
        (self.vault / '.knowledge/sources.json').write_text('{}')
        self.commit('theirs')
        before = self.git('status', '--porcelain=v1')
        index = (self.repo / '.git/index').read_bytes()
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['base'], self.base)
        self.assertTrue(report['needs_review'])
        self.assertEqual(report['shared_canonical_paths'], ['vault/both.md', 'vault/old.md', 'vault/shared.md'])
        self.assertEqual(report['duplicate_ids'], [{'id': 'same-id', 'ours': ['vault/a.md'], 'theirs': ['vault/b.md']}])
        self.assertTrue(any(x['status'].startswith('R') for x in report['changes']['ours']))
        self.assertTrue(any(x['status'] == 'D' for x in report['changes']['theirs']))
        self.assertTrue(report['reviewed_state']['.knowledge/review.json']['different'])
        self.assertIsNotNone(report['reviewed_state']['.knowledge/review.json']['base'])
        self.assertIsNone(report['reviewed_state']['.knowledge/sources.json']['base'])
        self.assertEqual(before, self.git('status', '--porcelain=v1'))
        self.assertEqual(index, (self.repo / '.git/index').read_bytes())

    def test_disjoint_changes(self):
        self.note('left.md', 'left'); self.commit('left')
        self.git('checkout', '-b', 'theirs', self.base)
        self.note('right.md', 'right'); self.commit('right')
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report['needs_review'])
        self.assertEqual(report['shared_canonical_paths'], [])

    def test_missing_and_unrelated_refs_and_shallow(self):
        self.note('x.md', 'x'); self.commit('ours')
        self.assertEqual(self.call(theirs='missing').returncode, 1)
        self.git('checkout', '--orphan', 'theirs')
        self.git('rm', '-rf', '.')
        self.vault.mkdir(exist_ok=True)
        self.note('y.md', 'y'); self.commit('unrelated')
        result = self.call()
        self.assertEqual(result.returncode, 1)
        self.assertIn('no common merge base', result.stderr)
        clone = self.repo.parent / (self.repo.name + '-shallow')
        self.addCleanup(lambda: __import__('shutil').rmtree(clone, ignore_errors=True))
        subprocess.run(['git', 'clone', '--depth=1', '-q', self.repo.as_uri(), str(clone)], check=True)
        result = self.call(ours='HEAD', theirs='HEAD', repo=clone, vault=clone / 'vault')
        self.assertEqual(result.returncode, 1)
        self.assertIn('shallow history', result.stderr)

    def test_ambiguous_ref_and_multiple_merge_bases(self):
        self.note('x.md', 'x'); self.commit('ours')
        self.git('tag', 'ours', self.base)
        self.assertIn('ambiguous ref', self.call(ours='ours', theirs='HEAD').stderr)
        self.git('tag', '-d', 'ours')
        first = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-b', 'theirs', self.base)
        self.note('y.md', 'y'); self.commit('theirs')
        second = self.git('rev-parse', 'HEAD').strip()
        tree = self.git('rev-parse', 'HEAD^{tree}').strip()
        one = self.git('commit-tree', tree, '-p', first, '-p', second, '-m', 'merge one').strip()
        two = self.git('commit-tree', tree, '-p', second, '-p', first, '-m', 'merge two').strip()
        result = self.call(ours=one, theirs=two)
        self.assertEqual(result.returncode, 1)
        self.assertIn('multiple merge bases', result.stderr)

    def test_fresh_invocation_does_not_write_fixture_or_skill(self):
        self.note('left.md', 'left'); self.commit('left')
        self.git('checkout', '-b', 'theirs', self.base)
        self.note('right.md', 'right'); self.commit('right')
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'scripts'
            copied.mkdir()
            for name in ('merge.py', 'knowledge.py'):
                shutil.copy2(SCRIPT.parent / name, copied / name)
            def inventory(root):
                return {str(p.relative_to(root)): ('dir' if p.is_dir() else p.read_bytes())
                        for p in root.rglob('*') if not p.is_symlink()}
            before_repo, before_skill = inventory(self.repo), inventory(copied)
            env = dict(os.environ)
            env.pop('PYTHONDONTWRITEBYTECODE', None)
            result = subprocess.run(['python3', str(copied / 'merge.py'), 'inspect', '--repo', str(self.repo), '--vault', str(self.vault), '--ours', 'ours', '--theirs', 'theirs', '--json'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before_repo, inventory(self.repo))
            self.assertEqual(before_skill, inventory(copied))

    def test_partial_and_promisor_config_rejected_before_object_access(self):
        self.note('x.md', 'x'); self.commit('ours')
        for key, value in (('extensions.partialClone', 'origin'), ('remote.origin.promisor', 'true')):
            with self.subTest(key=key):
                self.git('config', key, value)
                result = self.call(ours='does-not-exist', theirs='HEAD')
                self.assertEqual(result.returncode, 1)
                self.assertIn('requires full local history', result.stderr)
                self.assertNotIn(value, result.stderr)
                self.git('config', '--unset', key)

    def test_symlink_blob_not_parsed_and_credential_paths_ignored(self):
        (self.vault / 'alias.md').symlink_to('old.md')
        (self.vault / '.env.md').write_text('---\nid: "secret"\n---\n')
        self.commit('unsafe')
        self.git('checkout', '-b', 'theirs', self.base)
        self.note('other.md', 'other'); self.commit('other')
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['skipped_id_paths']['ours'][0]['reason'], 'not a regular file blob')
        self.assertNotIn('.env.md', result.stdout)
        self.assertTrue(report['needs_review'])


if __name__ == '__main__':
    unittest.main()
