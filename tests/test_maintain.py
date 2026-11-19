import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'skills/project-knowledge/scripts'))
import maintain  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / 'skills/project-knowledge/scripts' / 'maintain.py'


class MaintainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.vault = self.repo / 'vault'
        (self.vault / '.knowledge').mkdir(parents=True)
        (self.vault / 'runs').mkdir()
        self.note('area.md', 'area', 'area', [], [])
        self.note('note.md', 'note', 'note', ['area'], ['source.txt'])
        self.note('runs/review.md', 'review', 'run', [], [])
        (self.repo / 'source.txt').write_text('one')
        (self.vault / '.knowledge/sources.json').write_text(json.dumps({'note': {'source.txt': self.sha(self.repo / 'source.txt')}}))
        self.git('add', '.')
        self.git('commit', '-m', 'initial')
        base = self.git('rev-parse', 'HEAD').strip()
        (self.vault / '.knowledge/review.json').write_text(json.dumps({'schema': 1, 'ref': 'refs/heads/main', 'reviewed_through': base, 'coverage': 'partial'}))
        self.git('add', '.')
        self.git('commit', '-m', 'cursor')

    def note(self, name, ident, kind, areas, sources):
        data = {'id': ident, 'title': ident, 'type': kind, 'status': 'current', 'areas': areas, 'sources': sources, 'updated': '2026-01-01'}
        (self.vault / name).write_text('---\n' + ''.join(k + ': ' + json.dumps(v) + '\n' for k, v in data.items()) + '---\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def cli(self, *args, ok=True, code=None):
        p = subprocess.run(['python3', str(SCRIPT), *args, '--repo', str(self.repo), '--vault', str(self.vault)], capture_output=True, text=True)
        self.assertEqual(p.returncode, code if code is not None else (0 if ok else 1), p.stderr + p.stdout)
        return p

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def change(self):
        (self.repo / 'source.txt').write_text('two')
        self.git('add', 'source.txt')
        self.git('commit', '-m', 'change')

    def plan(self):
        initial = json.loads(self.cli('scan', '--json').stdout)
        run = self.vault / 'runs/review.md'
        content = run.read_text()
        content = content.replace('---\n', '---\n' + 'review_base: ' + json.dumps(initial['base']) + '\nreview_target: ' + json.dumps(initial['target']) + '\n', 1)
        lines = content.splitlines()
        seen = set(); filtered = []
        for line in lines:
            key = line.partition(':')[0]
            if key in ('review_base', 'review_target'):
                if key in seen:
                    continue
                seen.add(key)
            filtered.append(line)
        run.write_text('\n'.join(filtered) + '\n')
        self.cli('scan', '--write-status')
        path = self.vault / '.knowledge/sync-plan.json'
        return path, json.loads(path.read_text())

    def receipt(self, planpath, plan):
        result = {'plan_sha256': self.sha(planpath), 'paths': {p: {'status': 'reviewed', 'reason': 'inspected'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}
        path = self.repo / 'receipt.json'
        path.write_text(json.dumps(result))
        return path

    def test_scan_read_only_and_old_reverted_changes(self):
        self.change()
        self.git('revert', '--no-edit', 'HEAD')
        before = self.git('status', '--porcelain')
        p = json.loads(self.cli('scan', '--json').stdout)
        self.assertIn('source.txt', p['paths'])
        self.assertEqual(before, self.git('status', '--porcelain'))
        self.assertEqual(p['affected_notes'], ['note'])

    def test_rename_untracked_and_credential_exclusion(self):
        self.git('mv', 'source.txt', 'new name.txt')
        self.git('commit', '-m', 'rename')
        (self.repo / 'new file.txt').write_text('new')
        (self.repo / '.env').write_text('secret')
        p = json.loads(self.cli('scan', '--json').stdout)
        self.assertEqual(p['paths'], ['new name.txt', 'source.txt'])
        self.assertIn('new file.txt', p['dirty'])
        self.assertNotIn('.env', str(p))
        self.assertTrue(p['errors'])

    def test_published_knowledge_bundle_does_not_queue_its_own_files(self):
        new_vault = self.repo / 'knowledge' / 'example'
        shutil.copytree(self.vault, new_vault)
        self.vault = new_vault
        cursor = new_vault / '.knowledge/review.json'
        checkpoint = json.loads(cursor.read_text())
        checkpoint['reviewed_through'] = self.git('rev-parse', 'HEAD').strip()
        cursor.write_text(json.dumps(checkpoint))
        (self.repo / 'knowledge/README.md').write_text('How to run the skill')
        (self.repo / 'knowledge/.gitignore').write_text('__pycache__/\n')
        self.git('add', 'knowledge')
        self.git('commit', '-m', 'publish knowledge bundle')
        (self.repo / 'knowledge/README.md').write_text('Updated skill instructions')
        (self.repo / 'knowledge/product-spec.md').write_text('Actual project scope')
        self.change()

        plan = json.loads(self.cli('scan', '--json').stdout)
        self.assertEqual(plan['paths'], ['source.txt'])
        self.assertEqual(plan['dirty'], ['knowledge/product-spec.md'])
        self.assertEqual(plan['affected_notes'], ['note'])

    def test_finish_and_noop(self):
        self.change()
        planpath, plan = self.plan()
        receipt = self.receipt(planpath, plan)
        # Receipt is outside reviewed evidence and must exist before scanning.
        receipt.unlink()
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(planpath), 'paths': {p: {'status': 'reviewed', 'reason': 'inspected'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        self.cli('finish', '--plan', str(planpath), '--review', str(receipt))
        cursor = json.loads((self.vault / '.knowledge/review.json').read_text())
        self.assertEqual(cursor['reviewed_through'], self.git('rev-parse', 'HEAD').strip())
        baseline = json.loads((self.vault / '.knowledge/sources.json').read_text())
        self.assertEqual(baseline['note']['source.txt'], self.sha(self.repo / 'source.txt'))
        newpath, newplan = self.plan()
        self.assertEqual(newplan['paths'], [])

    def test_merge_and_revert_include_side_history(self):
        self.git('checkout', '-b', 'feature')
        self.change()
        self.git('revert', '--no-edit', 'HEAD')
        self.git('checkout', 'main')
        self.git('merge', '--no-ff', '-m', 'merge feature', 'feature')
        plan = json.loads(self.cli('scan', '--json').stdout)
        self.assertIn('source.txt', plan['paths'])
        self.assertGreaterEqual(len(plan['commits']), 3)

    def test_non_checkout_target_is_blocked(self):
        self.git('checkout', '-b', 'feature')
        self.change()
        target = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', 'main')
        plan = json.loads(self.cli('scan', '--target', target, '--json').stdout)
        self.assertTrue(any('target is not checked out' in b for b in plan['blockers']))

    def test_old_commit_and_shared_cursor_fresh_clone(self):
        (self.repo / 'source.txt').write_text('old change')
        self.git('add', 'source.txt')
        env = dict(os.environ, GIT_AUTHOR_DATE='2020-01-01T12:00:00+0000', GIT_COMMITTER_DATE='2020-01-01T12:00:00+0000')
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-m', 'old'], env=env, check=True, capture_output=True)
        clone = self.repo.parent / (self.repo.name + '-clone')
        self.addCleanup(lambda: __import__('shutil').rmtree(clone, ignore_errors=True))
        subprocess.run(['git', 'clone', '-q', str(self.repo), str(clone)], check=True)
        p = subprocess.run(['python3', str(SCRIPT), 'scan', '--repo', str(clone), '--vault', str(clone / 'vault'), '--json'], capture_output=True, text=True, check=True)
        plan = json.loads(p.stdout)
        self.assertIn('source.txt', plan['paths'])
        self.assertEqual(plan['base'], json.loads((clone / 'vault/.knowledge/review.json').read_text())['reviewed_through'])
        self.assertEqual(len(plan['commits']), 2)

    def test_shallow_history_blocks_and_missing_cursor_errors(self):
        self.change()
        clone = self.repo.parent / (self.repo.name + '-shallow')
        self.addCleanup(lambda: __import__('shutil').rmtree(clone, ignore_errors=True))
        subprocess.run(['git', 'clone', '-q', '--depth=1', self.repo.as_uri(), str(clone)], check=True)
        p = subprocess.run(['python3', str(SCRIPT), 'scan', '--repo', str(clone), '--vault', str(clone / 'vault'), '--json'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn('ERROR:', p.stderr)
        self.assertNotEqual(json.loads((clone / 'vault/.knowledge/review.json').read_text())['reviewed_through'], subprocess.run(['git', '-C', str(clone), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip())
        (self.vault / '.knowledge/review.json').unlink()
        self.cli('scan', ok=False)

    def test_diverged_cursor_blocked(self):
        self.git('checkout', '-b', 'other')
        self.change()
        other = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', 'main')
        cursor = self.vault / '.knowledge/review.json'
        data = json.loads(cursor.read_text()); data['reviewed_through'] = other
        cursor.write_text(json.dumps(data))
        plan = json.loads(self.cli('scan', '--json').stdout)
        self.assertTrue(any('not an ancestor' in b for b in plan['blockers']))

    def test_selective_baseline_and_new_note_after_rescan(self):
        (self.repo / 'other.txt').write_text('other')
        self.note('other.md', 'other', 'note', ['area'], ['other.txt'])
        baseline_file = self.vault / '.knowledge/sources.json'
        baseline = json.loads(baseline_file.read_text()); baseline['other'] = {'other.txt': 'previous-reviewed-hash'}
        baseline_file.write_text(json.dumps(baseline))
        self.git('add', '.')
        self.git('commit', '-m', 'other note')
        cursor = self.vault / '.knowledge/review.json'
        data = json.loads(cursor.read_text()); data['reviewed_through'] = self.git('rev-parse', 'HEAD').strip()
        cursor.write_text(json.dumps(data))
        self.git('add', 'vault/.knowledge/review.json')
        self.git('commit', '-m', 'review other note')
        self.change()
        first, original = self.plan()
        self.note('added.md', 'added', 'note', ['area'], ['source.txt'])
        planpath, plan = self.plan()
        self.assertNotIn('added', original['affected_notes'])
        self.assertIn('added', plan['affected_notes'])
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(planpath), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        self.cli('finish', '--plan', str(planpath), '--review', str(receipt))
        result = json.loads(baseline_file.read_text())
        self.assertEqual(result['other'], {'other.txt': 'previous-reviewed-hash'})
        self.assertEqual(result['added']['source.txt'], self.sha(self.repo / 'source.txt'))

    def test_empty_finish_no_canonical_churn(self):
        planpath, plan = self.plan()
        self.assertEqual(plan['paths'], [])
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(planpath), 'paths': {}, 'notes': {}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        before = {p: self.sha(self.vault / p) for p in ('.knowledge/review.json', '.knowledge/sources.json')}
        self.cli('finish', '--plan', str(planpath), '--review', str(receipt))
        self.assertEqual(before, {p: self.sha(self.vault / p) for p in before})
        self.assertFalse((self.vault / 'graph.html').exists())

    def test_dirty_path_and_conflicts_block_finish(self):
        self.change()
        (self.repo / 'source.txt').write_text('uncommitted')
        planpath, plan = self.plan()
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(planpath), 'paths': {'source.txt': {'status': 'reviewed', 'reason': 'read'}}, 'notes': {'note': {'status': 'unchanged', 'expected_sha256': plan['notes']['note']['sha256']}}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        self.cli('finish', '--plan', str(planpath), '--review', str(receipt), ok=False)
        self.git('checkout', '--', 'source.txt')
        self.git('checkout', '-b', 'conflict')
        (self.repo / 'source.txt').write_text('branch')
        self.git('commit', '-am', 'branch')
        self.git('checkout', 'main')
        (self.repo / 'source.txt').write_text('main')
        self.git('commit', '-am', 'main')
        subprocess.run(['git', '-C', str(self.repo), 'merge', 'conflict'], capture_output=True)
        plan = json.loads(self.cli('scan', '--json').stdout)
        self.assertTrue(any('conflict' in b for b in plan['blockers']))

    def test_status_escapes_paths_and_skips_credential_aliases(self):
        name = '<script> & ü.txt'
        (self.repo / name).write_text('content')
        (self.repo / '.env').write_text('secret must not be read')
        (self.repo / 'alias').symlink_to('.env')
        self.cli('scan', '--write-status')
        plan = json.loads((self.vault / '.knowledge/sync-plan.json').read_text())
        self.assertEqual(plan['state'], 'pending')
        self.assertIn(name, plan['dirty'])
        self.assertIn('alias', plan['skipped_sources'])
        self.assertNotIn('alias', plan['source_hashes'])
        page = (self.vault / 'sync.html').read_text()
        self.assertIn('&lt;script&gt; &amp; ü.txt', page)
        self.assertNotIn('<script>', page)
        self.assertIn('knowledge.py serve', page)
        self.assertNotIn('secret must not be read', page)

    def test_freshness_and_dirty_note_visible(self):
        (self.repo / 'source.txt').write_text('dirty')
        self.cli('scan', '--write-status')
        report = json.loads((self.vault / '.knowledge/sync-plan.json').read_text())
        status = (self.vault / '.knowledge/sync-status.md').read_text()
        self.assertEqual(report['dirty_affected_notes'], ['note'])
        self.assertEqual(report['state'], 'pending')
        self.assertIn('Source freshness warnings', status)
        self.assertIn('source.txt', status)
        self.assertIn(report['scanned_at'], status)

    def test_deleted_source_repointed_note_remains_affected(self):
        (self.repo / 'alternate.txt').write_text('alternate')
        self.git('add', 'alternate.txt')
        self.git('commit', '-m', 'alternate')
        self.git('rm', 'source.txt')
        self.git('commit', '-m', 'delete original')
        self.note('note.md', 'note', 'note', ['area'], ['alternate.txt'])
        planpath, plan = self.plan()
        self.assertIn('note', plan['affected_notes'])
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(planpath), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'updated', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        self.cli('finish', '--plan', str(planpath), '--review', str(receipt))
        baseline = json.loads((self.vault / '.knowledge/sources.json').read_text())
        self.assertEqual(baseline['note'], {'alternate.txt': self.sha(self.repo / 'alternate.txt')})

    def test_tampered_impact_cannot_advance_cursor(self):
        self.change()
        path, plan = self.plan()
        before = self.sha(self.vault / '.knowledge/review.json')
        plan['affected_notes'] = []
        path.write_text(json.dumps(plan))
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(path), 'paths': {'source.txt': {'status': 'reviewed', 'reason': 'read'}}, 'notes': {}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=False)
        self.assertEqual(before, self.sha(self.vault / '.knowledge/review.json'))

    def test_symlink_and_dot_path_cannot_accept_dirty_evidence(self):
        (self.repo / 'other.txt').write_text('clean')
        (self.repo / 'alias.txt').symlink_to('other.txt')
        self.note('note.md', 'note', 'note', ['area'], ['source.txt', 'alias.txt'])
        self.git('add', '.')
        self.git('commit', '-m', 'alias')
        cursor = self.vault / '.knowledge/review.json'
        data = json.loads(cursor.read_text()); data['reviewed_through'] = self.git('rev-parse', 'HEAD').strip()
        cursor.write_text(json.dumps(data))
        self.git('add', 'vault/.knowledge/review.json')
        self.git('commit', '-m', 'review alias')
        self.change()
        (self.repo / 'other.txt').write_text('dirty')
        path, plan = self.plan()
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(path), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        failure = self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=False)
        self.assertIn('cites aliased evidence', failure.stderr)
        self.note('note.md', 'note', 'note', ['area'], ['source.txt', './other.txt'])
        path, plan = self.plan()
        receipt.write_text(json.dumps({'plan_sha256': self.sha(path), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        failure = self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=False)
        self.assertIn('cites dirty evidence', failure.stderr)
        self.assertIn('note', plan['dirty_affected_notes'])

    def test_run_provenance_rejects_wrong_type_range_and_hash(self):
        self.change()
        planpath, initial = self.plan()
        run = self.vault / 'runs/review.md'
        valid = run.read_text()
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        for mode in ('type', 'range', 'hash'):
            with self.subTest(mode=mode):
                content = valid
                if mode == 'type':
                    content = content.replace('type: "run"', 'type: "index"')
                if mode == 'range':
                    content = content.replace(initial['target'], '0' * 40)
                run.write_text(content)
                self.cli('scan', '--write-status')
                plan = json.loads(planpath.read_text())
                receipt.write_text(json.dumps({'plan_sha256': self.sha(planpath), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': '0' * 64 if mode == 'hash' else self.sha(run)}))
                self.cli('finish', '--plan', str(planpath), '--review', str(receipt), ok=False)
        run.write_text(valid)

    def test_case_alias_and_hardlink_dirty_evidence(self):
        (self.repo / 'other.txt').write_text('clean')
        os.link(self.repo / 'other.txt', self.repo / 'hardlink.txt')
        self.git('add', 'other.txt', 'hardlink.txt')
        self.git('commit', '-m', 'other evidence')
        cursor = self.vault / '.knowledge/review.json'
        data = json.loads(cursor.read_text()); data['reviewed_through'] = self.git('rev-parse', 'HEAD').strip()
        cursor.write_text(json.dumps(data)); self.git('add', 'vault/.knowledge/review.json'); self.git('commit', '-m', 'review other')
        self.change()
        aliases = ['hardlink.txt']
        if (self.repo / 'OTHER.txt').exists():
            aliases.append('OTHER.txt')
        for alias in aliases:
            with self.subTest(alias=alias):
                (self.repo / 'other.txt').write_text('dirty')
                self.note('note.md', 'note', 'note', ['area'], ['source.txt', alias])
                path, plan = self.plan()
                receipt = self.repo.parent / (self.repo.name + '-receipt.json')
                self.addCleanup(lambda: receipt.unlink(missing_ok=True))
                receipt.write_text(json.dumps({'plan_sha256': self.sha(path), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
                failure = self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=False)
                self.assertIn('cites dirty evidence', failure.stderr)
                self.assertIn('note', plan['dirty_affected_notes'])

    def test_case_variant_impacts_changed_source(self):
        self.note('note.md', 'note', 'note', ['area'], ['SOURCE.txt'])
        self.change()
        plan = json.loads(self.cli('scan', '--json').stdout)
        self.assertIn('note', plan['affected_notes'])
        self.assertNotIn('source.txt', plan['unmapped'])

    def evidence_scenario(self, mode):
        extra = 'build/extra.txt' if mode == 'excluded' else 'extra.txt'
        file = self.repo / extra
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('committed')
        if mode != 'untracked':
            self.git('add', '-f', extra)
            self.git('commit', '-m', 'extra evidence')
        else:
            with (self.repo / '.git/info/exclude').open('a') as ignored:
                ignored.write('extra.txt\n')
        self.note('note.md', 'note', 'note', ['area'], ['source.txt', extra])
        self.change()
        if mode in ('excluded', 'assume', 'skip'):
            if mode == 'assume':
                self.git('update-index', '--assume-unchanged', extra)
            if mode == 'skip':
                self.git('update-index', '--skip-worktree', extra)
            file.write_text('uncommitted')
        path, plan = self.plan()
        self.assertNotIn(extra, plan['dirty'])
        receipt = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(path), 'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']}, 'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        cursor = self.vault / '.knowledge/review.json'
        baseline = self.vault / '.knowledge/sources.json'
        before = (cursor.read_bytes(), baseline.read_bytes())
        result = self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=mode == 'clean')
        if mode == 'clean':
            self.assertEqual(json.loads(cursor.read_text())['reviewed_through'], plan['target'])
            self.assertEqual(json.loads(baseline.read_text())['note'][extra], self.sha(file))
        else:
            self.assertEqual((cursor.read_bytes(), baseline.read_bytes()), before)
            self.assertIn('not tracked in target' if mode == 'untracked' else 'dirty evidence', result.stderr)

    def test_ignored_untracked_selected_evidence_rejected(self):
        self.evidence_scenario('untracked')

    def test_excluded_dirty_selected_evidence_rejected(self):
        self.evidence_scenario('excluded')

    def test_assume_unchanged_selected_evidence_rejected(self):
        self.evidence_scenario('assume')

    def test_skip_worktree_selected_evidence_rejected(self):
        self.evidence_scenario('skip')

    def test_clean_tracked_extra_selected_evidence_accepted(self):
        self.evidence_scenario('clean')

    def test_deferred_and_race_rejected(self):
        self.change()
        path, plan = self.plan()
        receipt = Path(self.tmp.name).parent / (Path(self.tmp.name).name + '-receipt.json')
        self.addCleanup(lambda: receipt.unlink(missing_ok=True))
        receipt.write_text(json.dumps({'plan_sha256': self.sha(path), 'paths': {'source.txt': {'status': 'deferred', 'reason': 'later'}}, 'notes': {'note': {'status': 'unchanged', 'expected_sha256': plan['notes']['note']['sha256']}}, 'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}))
        self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=False)
        (self.repo / 'source.txt').write_text('raced')
        self.cli('finish', '--plan', str(path), '--review', str(receipt), ok=False)


    # scan performance, robustness and the receipt helper
    def test_scan_resolves_each_path_once(self):
        for i in range(30):
            sources = []
            for j in range(3):
                name = f'src/file{i}_{j}.txt'
                (self.repo / name).parent.mkdir(exist_ok=True)
                (self.repo / name).write_text('x')
                sources.append(name)
            self.note(f'n{i}.md', f'n{i}', 'note', ['area'], sources)
        self.git('add', '.')
        self.git('commit', '-m', 'notes')
        cursor = self.vault / '.knowledge/review.json'
        cursor.write_text(json.dumps({'schema': 1, 'ref': 'refs/heads/main', 'reviewed_through': self.git('rev-parse', 'HEAD').strip(), 'coverage': 'partial'}))
        self.git('add', '.')
        self.git('commit', '-m', 'cursor')
        for i in range(60):
            (self.repo / f'changed{i}.txt').write_text('y')
        (self.repo / 'src/file0_0.txt').write_text('changed')
        self.git('add', '.')
        self.git('commit', '-m', 'many')
        calls = []
        real = maintain.knowledge.safe_path
        with mock.patch.object(maintain.knowledge, 'safe_path', lambda *a: calls.append(a) or real(*a)):
            report = maintain.scan(self.repo.resolve(), self.vault.resolve(), None)
        self.assertEqual(len(report['paths']), 61)
        self.assertEqual([n for n in report['affected_notes'] if n.startswith('n') and n != 'note'], ['n0'])
        sources, paths = 90 + 1, len(report['paths'])
        # Quadratic matching would need sources * paths (several thousand) lookups; linear needs a few per path.
        self.assertLess(len(calls), 12 * (sources + paths), len(calls))
        evidence = maintain.Evidence(self.repo.resolve())
        before = len(calls)
        with mock.patch.object(maintain.knowledge, 'safe_path', lambda *a: calls.append(a) or real(*a)):
            group = evidence.group(['source.txt', 'changed1.txt'])
            for _ in range(50):
                self.assertTrue(evidence.matches(group, 'SOURCE.txt'))
                self.assertFalse(evidence.matches(group, 'other.txt'))
        self.assertEqual(len(calls) - before, 4)  # two group paths plus two distinct probes; repeats are cached
        self.assertTrue(maintain.same_evidence(self.repo.resolve(), 'Source.TXT', 'source.txt'))
        self.assertFalse(maintain.same_evidence(self.repo.resolve(), '../x', 'source.txt'))

    def test_non_utf8_path_in_range_does_not_crash_write_status(self):
        def index_info(line):
            subprocess.run(['git', '-C', str(self.repo), 'update-index', '--index-info'], input=line, check=True)
        blob = subprocess.run(['git', '-C', str(self.repo), 'hash-object', '-w', '--stdin'], input=b'data', capture_output=True, check=True).stdout.strip()
        index_info(b'100644 ' + blob + b'\tbad-\xff.txt\n')
        self.git('commit', '-m', 'add undecodable path')
        index_info(b'0 ' + b'0' * 40 + b'\tbad-\xff.txt\n')
        self.git('commit', '-m', 'remove it')
        planpath, plan = self.plan()
        self.assertTrue(any('bad-' in p for p in plan['paths']))
        self.assertIn('bad-', (self.vault / '.knowledge/sync-status.md').read_text())
        self.assertIn('bad-', (self.vault / 'sync.html').read_text())
        out = self.repo.parent / (self.repo.name + '-bad.json')
        self.addCleanup(lambda: out.unlink(missing_ok=True))
        self.cli('receipt', '--plan', str(planpath), '--out', str(out))
        data = json.loads(out.read_text())
        for entry in data['paths'].values():
            entry.update(status='reviewed', reason='read')
        out.write_text(json.dumps(data))
        self.cli('finish', '--plan', str(planpath), '--review', str(out))

    def receipt_cli(self, planpath, *extra, ok=True):
        out = self.repo.parent / (self.repo.name + '-receipt.json')
        self.addCleanup(lambda: out.unlink(missing_ok=True))
        p = self.cli('receipt', '--plan', str(planpath), '--out', str(out), *extra, ok=ok)
        return out, p

    def test_receipt_fills_hashes_and_leaves_review_empty(self):
        self.change()
        planpath, plan = self.plan()
        out, result = self.receipt_cli(planpath)
        data = json.loads(out.read_text())
        self.assertEqual(data['plan_sha256'], self.sha(planpath))
        self.assertEqual(data['paths'], {'source.txt': {'status': '', 'reason': ''}})
        self.assertEqual(data['notes'], {'note': {'status': '', 'expected_sha256': self.sha(self.vault / 'note.md')}})
        self.assertEqual((data['run_path'], data['run_sha256']), ('runs/review.md', self.sha(self.vault / 'runs/review.md')))
        self.assertIn('1 paths', result.stdout)
        # finish still demands a real review
        self.cli('finish', '--plan', str(planpath), '--review', str(out), ok=False)
        data['paths']['source.txt'].update(status='reviewed', reason='   ')
        data['notes']['note']['status'] = 'unchanged'
        out.write_text(json.dumps(data))
        self.cli('finish', '--plan', str(planpath), '--review', str(out), ok=False)
        data['paths']['source.txt']['reason'] = 'read the diff'
        out.write_text(json.dumps(data))
        self.cli('finish', '--plan', str(planpath), '--review', str(out))
        self.assertEqual(json.loads((self.vault / '.knowledge/review.json').read_text())['reviewed_through'], self.git('rev-parse', 'HEAD').strip())

    def test_receipt_carries_over_only_what_was_reviewed(self):
        self.change()
        planpath, plan = self.plan()
        out, _ = self.receipt_cli(planpath)
        data = json.loads(out.read_text())
        data['paths']['source.txt'].update(status='reviewed', reason='kept')
        data['paths']['gone.txt'] = {'status': 'reviewed', 'reason': 'no longer applies'}
        data['notes']['note']['status'] = 'updated'
        data['notes']['gone'] = {'status': 'updated', 'expected_sha256': 'x'}
        out.write_text(json.dumps(data))
        # Same plan, same note bytes: dispositions stay, stale entries drop.
        self.cli('receipt', '--plan', str(planpath), '--out', str(out))
        fresh = json.loads(out.read_text())
        self.assertEqual(fresh['paths'], {'source.txt': {'status': 'reviewed', 'reason': 'kept'}})
        self.assertEqual(fresh['notes'], {'note': {'status': 'updated', 'expected_sha256': self.sha(self.vault / 'note.md')}})
        # A receipt for another plan must not leave its path dispositions behind.
        data = json.loads(out.read_text())
        data['plan_sha256'] = '0' * 64
        out.write_text(json.dumps(data))
        self.cli('receipt', '--plan', str(planpath), '--out', str(out))
        fresh = json.loads(out.read_text())
        self.assertEqual(fresh['paths'], {'source.txt': {'status': '', 'reason': ''}})
        self.assertEqual(fresh['notes']['note']['status'], 'updated')
        # A note whose bytes changed since the entered disposition loses it; the hash is refreshed.
        data = json.loads(out.read_text())
        data['notes']['note']['expected_sha256'] = '1' * 64
        out.write_text(json.dumps(data))
        self.cli('receipt', '--plan', str(planpath), '--out', str(out))
        fresh = json.loads(out.read_text())
        self.assertEqual(fresh['notes']['note'], {'status': '', 'expected_sha256': self.sha(self.vault / 'note.md')})

    def test_receipt_run_selection_and_empty_plan(self):
        planpath, plan = self.plan()
        self.assertEqual(plan['paths'], [])
        out, _ = self.receipt_cli(planpath)
        self.assertNotIn('run_path', json.loads(out.read_text()))
        self.change()
        planpath, plan = self.plan()
        out, _ = self.receipt_cli(planpath, '--run', str(self.vault / 'runs/review.md'))
        self.assertEqual(json.loads(out.read_text())['run_path'], 'runs/review.md')
        out, _ = self.receipt_cli(planpath, '--run', 'runs/review.md')
        self.assertEqual(json.loads(out.read_text())['run_path'], 'runs/review.md')
        self.receipt_cli(planpath, '--run', 'runs/missing.md', ok=False)
        self.receipt_cli(planpath, '--run', 'note.md', ok=False)
        self.note('runs/other.md', 'other', 'run', [], [])
        (self.vault / 'runs/other.md').write_text((self.vault / 'runs/review.md').read_text().replace('id: "review"', 'id: "other"'))
        self.cli('scan', '--write-status')
        planpath = self.vault / '.knowledge/sync-plan.json'
        self.receipt_cli(planpath, ok=False)  # ambiguous: two run notes carry the range


    def closed_gap_fixture(self, decision='done', plan=False):
        sections = ''.join(f'## {n}\n\ntext\n\n' for n in ('Current behavior', 'Gap', 'Evidence', 'Recheck', 'Discussion', 'Decision'))
        (self.vault / 'gaps').mkdir(exist_ok=True)
        (self.repo / 'gone.txt').write_text('soon deleted')
        extra = '' if decision == 'done' else 'decided_by: "Ann"\ndecided_on: "2026-11-15"\n'
        gap = ('---\nid: "g"\ntitle: "g"\ntype: "gap"\nareas: ["area"]\nsources: ["gone.txt"]\nupdated: "2026-01-01"\n'
               f'kind: "product-gap"\nrecheck: "not-checked"\ndecision: "{decision}"\n{extra}---\n{sections}')
        (self.vault / 'gaps/g.md').write_text(gap)
        if plan:
            (self.vault / 'plans').mkdir(exist_ok=True)
            (self.vault / 'plans/p.md').write_text('---\nid: "p"\ntitle: "p"\ntype: "plan"\nstatus: "planned"\nareas: ["area"]\nsources: ["gone.txt"]\nupdated: "2026-01-01"\ngap: "g"\n---\nplan')
        self.git('add', '.')
        self.git('commit', '-m', 'gap')
        cursor = self.vault / '.knowledge/review.json'
        cursor.write_text(json.dumps({'schema': 1, 'ref': 'refs/heads/main', 'reviewed_through': self.git('rev-parse', 'HEAD').strip(), 'coverage': 'partial'}))
        self.git('add', '.')
        self.git('commit', '-m', 'cursor')
        self.git('rm', 'gone.txt')
        self.git('commit', '-m', 'delete')

    def finish_with_receipt(self, ok=True):
        planpath, plan = self.plan()
        out = self.repo.parent / (self.repo.name + '-closed.json')
        self.addCleanup(lambda: out.unlink(missing_ok=True))
        self.cli('receipt', '--plan', str(planpath), '--out', str(out))
        data = json.loads(out.read_text())
        for entry in data['paths'].values():
            entry.update(status='reviewed', reason='read')
        for entry in data['notes'].values():
            entry['status'] = 'unchanged'
        out.write_text(json.dumps(data))
        return plan, self.cli('finish', '--plan', str(planpath), '--review', str(out), ok=ok)

    def test_finish_with_closed_gap_whose_source_was_deleted(self):
        self.closed_gap_fixture('done', plan=True)
        plan, _ = self.finish_with_receipt()
        self.assertIn('g', plan['affected_notes'])
        self.assertIn('p', plan['affected_notes'])

    def test_finish_with_live_gap_and_deleted_source_is_refused(self):
        self.closed_gap_fixture('accepted')
        planpath, plan = self.plan()
        self.assertTrue(any('missing or not a file' in e for e in plan['errors']), plan['errors'])
        _, result = self.finish_with_receipt(ok=False)
        self.assertNotIn('KeyError', result.stderr)
        self.assertIn('structural errors', result.stderr + result.stdout)

    def test_finish_writes_reviewed_state_and_generates_nothing(self):
        self.closed_gap_fixture('done')
        self.finish_with_receipt()
        for name in ('AS-BUILT.md', 'GAPS.md', 'graph.html', 'Map.canvas', '.knowledge/graph.json'):
            self.assertFalse((self.vault / name).exists(), name)
        self.assertTrue((self.vault / '.knowledge/sources.json').is_file())


    def test_relevant_folds_lookalike_credential_and_ignored_names(self):
        for path in ('.\u017f\u017fh/id_r\u017fa', 'a/.GIT/config', 'x/NODE_MODULES/y.js', 'prod.tfvars', 'home/.kube/config'):
            with self.subTest(path=path):
                self.assertFalse(maintain.relevant(path, 'vault'))
        self.assertTrue(maintain.relevant('src/app.py', 'vault'))
        # a copy of the skill inside the repository is not the application, wherever the vault is
        for path in ('.claude/skills/project-knowledge/SKILL.md', '.agents/skills/project-knowledge/scripts/knowledge.py', 'knowledge/tooling/project-knowledge/SKILL.md', 'project-spec/notes/a.md'):
            self.assertFalse(maintain.relevant(path, 'project-spec'), path)
        self.assertTrue(maintain.relevant('.claude/skills/other-skill/SKILL.md', 'project-spec'))


    # partial finish, retargeting and receipt reporting
    def two_note_range(self):
        """note cites source.txt, other cites other.txt; both change in the range and other.txt is then left dirty."""
        (self.repo / 'other.txt').write_text('other')
        self.note('other.md', 'other', 'note', ['area'], ['other.txt'])
        baseline_file = self.vault / '.knowledge/sources.json'
        baseline = json.loads(baseline_file.read_text()); baseline['other'] = {'other.txt': self.sha(self.repo / 'other.txt')}
        baseline_file.write_text(json.dumps(baseline))
        self.git('add', '.')
        self.git('commit', '-m', 'other note')
        cursor = self.vault / '.knowledge/review.json'
        data = json.loads(cursor.read_text()); data['reviewed_through'] = self.git('rev-parse', 'HEAD').strip()
        cursor.write_text(json.dumps(data))
        self.git('add', '.')
        self.git('commit', '-m', 'cursor')
        (self.repo / 'source.txt').write_text('two')
        (self.repo / 'other.txt').write_text('other two')
        self.git('add', '.')
        self.git('commit', '-m', 'change both')
        (self.repo / 'other.txt').write_text('someone elses uncommitted edit')

    def write_receipt(self, planpath, plan, paths=None, notes=None):
        data = {'plan_sha256': self.sha(planpath),
                'paths': {p: {'status': 'reviewed', 'reason': 'read'} for p in plan['paths']},
                'notes': {n: {'status': 'unchanged', 'expected_sha256': plan['notes'][n]['sha256']} for n in plan['affected_notes']},
                'run_path': 'runs/review.md', 'run_sha256': self.sha(self.vault / 'runs/review.md')}
        for path, entry in (paths or {}).items():
            data['paths'][path] = entry
        for ident, entry in (notes or {}).items():
            data['notes'][ident] = {'expected_sha256': plan['notes'][ident]['sha256'], **entry}
        out = self.repo.parent / (self.repo.name + '-partial.json')
        self.addCleanup(lambda: out.unlink(missing_ok=True))
        out.write_text(json.dumps(data))
        return out

    def state(self):
        return {name: (self.vault / name).read_bytes() if (self.vault / name).exists() else None
                for name in ('.knowledge/review.json', '.knowledge/sources.json')}

    def test_partial_finish_accepts_clean_notes_and_leaves_checkpoint(self):
        self.two_note_range()
        planpath, plan = self.plan()
        self.assertEqual(plan['dirty_affected_notes'], ['other'])
        receipt = self.write_receipt(planpath, plan,
                                     paths={'other.txt': {'status': 'deferred', 'reason': 'owner has uncommitted edits'}},
                                     notes={'other': {'status': 'deferred', 'reason': 'waits for other.txt'}})
        before = self.state()
        checkpoint = json.loads(before['.knowledge/review.json'])['reviewed_through']
        result = self.cli('finish', '--plan', str(planpath), '--review', str(receipt), code=3)
        self.assertIn(f'partial: accepted 1 notes; deferred 1 paths, 1 notes; checkpoint stays at {checkpoint}', result.stdout)
        self.assertIn('deferred path other.txt: owner has uncommitted edits', result.stdout)
        self.assertIn('deferred note other: waits for other.txt', result.stdout)
        after = self.state()
        self.assertEqual(after['.knowledge/review.json'], before['.knowledge/review.json'])
        baseline = json.loads(after['.knowledge/sources.json'])
        self.assertEqual(baseline['note'], {'source.txt': self.sha(self.repo / 'source.txt')})
        self.assertEqual(baseline['other'], json.loads(before['.knowledge/sources.json'])['other'])  # deferred note keeps its fingerprint
        # The interval is still pending: the deferred path is listed, the accepted note has no freshness warning.
        again = json.loads(self.cli('scan', '--json').stdout)
        self.assertEqual(again['paths'], ['other.txt', 'source.txt'])
        self.assertTrue(any('other.md' in w for w in again['warnings']))
        self.assertFalse(any('note.md' in w for w in again['warnings']))
        self.assertEqual(again['state'], 'pending')
        # Once the other contributor's edit is committed, a full finish over the same range advances the checkpoint.
        self.git('add', '.')
        self.git('commit', '-m', 'their edit')
        (self.vault / 'runs/review.md').write_text((self.vault / 'runs/review.md').read_text().replace(plan['target'], self.git('rev-parse', 'HEAD').strip()))
        planpath, plan = self.plan()
        self.assertEqual(plan['base'], checkpoint)
        self.assertEqual(plan['dirty'], [])
        receipt = self.write_receipt(planpath, plan)
        result = self.cli('finish', '--plan', str(planpath), '--review', str(receipt))
        self.assertIn('review checkpoint advanced to', result.stdout)
        self.assertEqual(json.loads((self.vault / '.knowledge/review.json').read_text())['reviewed_through'], plan['target'])

    def test_partial_finish_rejects_accepting_what_is_dirty_or_deferred(self):
        self.two_note_range()
        planpath, plan = self.plan()
        deferred = {'other.txt': {'status': 'deferred', 'reason': 'later'}}
        before = self.state()
        cases = {
            'updated note cites dirty source': (deferred, {'other': {'status': 'updated'}}, 'cites dirty evidence'),
            'unchanged note cites deferred path': (deferred, {'other': {'status': 'unchanged'}}, 'cites dirty evidence'),
            'dirty path marked reviewed': ({}, {'other': {'status': 'deferred', 'reason': 'x'}}, 'dirty integrated path must be deferred'),
            'deferred path without reason': ({'other.txt': {'status': 'deferred', 'reason': ' '}}, {'other': {'status': 'deferred', 'reason': 'x'}}, 'reviewed/excluded/deferred'),
            'deferred note without reason': (deferred, {'other': {'status': 'deferred'}}, 'deferred note needs a reason'),
            'unknown path status': ({'other.txt': {'status': 'later', 'reason': 'x'}}, {}, 'reviewed/excluded/deferred'),
            'empty note status': (deferred, {'other': {'status': ''}}, 'updated/unchanged/deferred'),
        }
        for name, (paths, notes, message) in cases.items():
            with self.subTest(name):
                result = self.cli('finish', '--plan', str(planpath), '--review', str(self.write_receipt(planpath, plan, paths, notes)), ok=False)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.state(), before)
        # A clean path that is deferred makes every note citing it deferred too.
        self.git('checkout', '--', 'other.txt')
        planpath, plan = self.plan()
        receipt = self.write_receipt(planpath, plan, paths={'source.txt': {'status': 'deferred', 'reason': 'unsure'}})
        result = self.cli('finish', '--plan', str(planpath), '--review', str(receipt), ok=False)
        self.assertIn('cites a deferred path (mark the note deferred): note', result.stderr)
        self.assertEqual(self.state(), before)

    def test_partial_finish_keeps_lock_drift_and_rollback(self):
        self.two_note_range()
        planpath, plan = self.plan()
        receipt = self.write_receipt(planpath, plan, paths={'other.txt': {'status': 'deferred', 'reason': 'later'}},
                                     notes={'other': {'status': 'deferred', 'reason': 'later'}})
        before = self.state()
        lock = self.vault / '.knowledge/sync.lock'
        lock.write_text('')
        self.assertIn('lock already exists', self.cli('finish', '--plan', str(planpath), '--review', str(receipt), ok=False).stderr)
        lock.unlink()
        (self.repo / 'source.txt').write_text('raced')  # drift after the scan
        self.assertIn('plan changed', self.cli('finish', '--plan', str(planpath), '--review', str(receipt), ok=False).stderr)
        (self.repo / 'source.txt').write_text('two')
        self.assertEqual(self.state(), before)
        real, calls = maintain.atomic, []

        def failing(path, data):
            calls.append(path.name)
            if path.name == 'sources.json' and calls.count('sources.json') == 1:
                raise OSError('disk full')
            return real(path, data)
        with mock.patch.object(maintain, 'atomic', failing), self.assertRaises(OSError):
            maintain.finish(self.repo.resolve(), self.vault.resolve(), planpath, receipt)
        self.assertEqual(self.state(), before)  # published files restored, checkpoint never touched
        self.assertFalse(lock.exists())

    def test_finish_names_the_vault_commit_that_moved_head(self):
        self.change()
        planpath, plan = self.plan()
        out, _ = self.receipt_cli(planpath)
        (self.vault / 'note.md').write_text((self.vault / 'note.md').read_text() + 'prose\n')
        self.git('add', '.')
        self.git('commit', '-m', 'vault only')
        head = self.git('rev-parse', 'HEAD').strip()
        for result in (self.cli('finish', '--plan', str(planpath), '--review', str(out), ok=False),
                       self.cli('receipt', '--plan', str(planpath), '--out', str(out), ok=False)):
            self.assertIn('every commit in between touches only excluded paths', result.stderr)
            self.assertIn('scan --write-status', result.stderr)
            self.assertIn('review_target: ' + head, result.stderr)
            self.assertIn('regenerate the receipt', result.stderr)
        # An application commit on top is the ordinary drift error instead.
        (self.repo / 'source.txt').write_text('three')
        self.git('commit', '-am', 'application')
        for result in (self.cli('finish', '--plan', str(planpath), '--review', str(out), ok=False),):
            self.assertIn('plan changed: head', result.stderr)
            self.assertNotIn('excluded paths', result.stderr)
        # The documented recovery works: rescan, retarget the run page, regenerate the receipt, finish.
        self.git('reset', '--hard', head)
        planpath, plan = self.plan()
        self.assertEqual(plan['target'], head)

    def test_documented_retarget_order_reaches_a_successful_finish(self):
        self.change()
        planpath, plan = self.plan()
        out, _ = self.receipt_cli(planpath)
        (self.vault / 'note.md').write_text((self.vault / 'note.md').read_text() + 'prose\n')
        self.git('add', '.')
        self.git('commit', '-m', 'vault only')
        head = self.git('rev-parse', 'HEAD').strip()
        message = self.cli('finish', '--plan', str(planpath), '--review', str(out), ok=False).stderr
        # Follow the order the message and sync.md give: run page first, then scan, receipt, dispositions, finish.
        self.assertLess(message.index('review_target: ' + head), message.index('scan --write-status'))
        self.assertLess(message.index('scan --write-status'), message.index('"receipt"'))
        run = self.vault / 'runs/review.md'
        run.write_text(run.read_text().replace(plan['target'], head))
        self.cli('scan', '--write-status')
        planpath = self.vault / '.knowledge/sync-plan.json'
        plan = json.loads(planpath.read_text())
        self.assertEqual(plan['target'], head)
        out, _ = self.receipt_cli(planpath)
        data = json.loads(out.read_text())
        data['paths'] = {p: {'status': 'reviewed', 'reason': 'read'} for p in data['paths']}
        data['notes'] = {n: {**v, 'status': 'unchanged'} for n, v in data['notes'].items()}
        out.write_text(json.dumps(data))
        self.assertIn('review checkpoint advanced to ' + head, self.cli('finish', '--plan', str(planpath), '--review', str(out)).stdout)

    def test_partial_finish_exit_status_is_not_the_usage_error_status(self):
        self.assertEqual(maintain.PARTIAL_EXIT, 3)
        self.assertEqual(subprocess.run(['python3', str(SCRIPT), 'finish'], capture_output=True).returncode, 2)

    def test_receipt_reports_what_it_kept_and_reset(self):
        self.two_note_range()
        self.git('checkout', '--', 'other.txt')
        planpath, plan = self.plan()
        out, first = self.receipt_cli(planpath)
        self.assertNotIn('dispositions', first.stdout)  # nothing entered yet
        data = json.loads(out.read_text())
        for entry in data['paths'].values():
            entry.update(status='reviewed', reason='read')
        for entry in data['notes'].values():
            entry['status'] = 'unchanged'
        data['notes']['other'].update(status='deferred', reason='later')
        out.write_text(json.dumps(data))
        same = self.cli('receipt', '--plan', str(planpath), '--out', str(out)).stdout
        self.assertIn('dispositions kept: 2 paths, 2 notes; reset: 0 paths, 0 notes; dropped (no longer in the plan): 0 paths, 0 notes', same)
        self.assertEqual(json.loads(out.read_text())['notes']['other']['reason'], 'later')
        # Change one note file and the plan: its disposition and every path disposition are reset, with reasons.
        (self.vault / 'other.md').write_text((self.vault / 'other.md').read_text() + 'edited\n')
        (self.repo / 'third.txt').write_text('x')
        self.git('add', '.')
        self.git('commit', '-m', 'third')
        planpath, plan = self.plan()
        result = self.cli('receipt', '--plan', str(planpath), '--out', str(out)).stdout
        self.assertIn('kept: 0 paths, 1 notes', result)
        self.assertIn('reset: 2 paths (plan changed since the receipt was written), 1 notes (note file changed: other)', result)

if __name__ == '__main__':
    unittest.main()