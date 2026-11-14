import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('maintain.py')


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

    def cli(self, *args, ok=True):
        p = subprocess.run(['python3', str(SCRIPT), *args, '--repo', str(self.repo), '--vault', str(self.vault)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0 if ok else 1, p.stderr + p.stdout)
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
        self.assertIn('href="graph.html"', page)
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


if __name__ == '__main__':
    unittest.main()
