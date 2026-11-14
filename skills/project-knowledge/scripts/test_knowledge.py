import importlib.util
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('knowledge', Path(__file__).with_name('knowledge.py'))
k = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.vault = self.root / 'vault'
        self.repo.mkdir()
        self.vault.mkdir()
        (self.repo / 'source.txt').write_text('evidence', encoding='utf-8')
        self.note('areas/a.md', 'a', 'area', areas=[])
        self.note('00-index.md', 'index', 'index', areas=[], body='[[areas/a]]')
        self.note('notes/n.md', 'n', 'note', sources=['source.txt'], body='Привет [[areas/a|область]] `[[missing]]`\n```\n[[missing]]\n```')

    def tearDown(self):
        self.temp.cleanup()

    def note(self, path, ident, kind='note', areas=None, sources=None, body=''):
        meta = {'id': ident, 'title': 'Тест ' + ident, 'type': kind, 'status': 'current',
                'areas': ['a'] if areas is None else areas, 'sources': sources or [], 'updated': '2026-11-14'}
        file = self.vault / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('---\n' + ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in meta.items()) + '---\n' + body, encoding='utf-8')

    def run_cli(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = k.main([*args, '--repo', str(self.repo), '--vault', str(self.vault)])
        return status, out.getvalue(), err.getvalue()

    def test_links_and_duplicates(self):
        self.assertEqual(self.run_cli('check')[0], 0)
        self.note('other/a.md', 'other', 'area', areas=[])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='[[a]] [[absent]]')
        self.note('notes/duplicate.md', 'n', sources=['source.txt'])
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 1)
        self.assertIn('ambiguous wikilink a', err)
        self.assertIn('missing wikilink absent', err)
        self.assertIn('duplicate id n', err)

    def test_missing_and_escaping_source(self):
        self.note('notes/n.md', 'n', sources=['missing', '../outside', '.env'])
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 1)
        self.assertIn('missing or not a file', err)
        self.assertIn('stay inside', err)
        self.assertIn('credential', err)
        (self.repo / 'escape').symlink_to(self.root, target_is_directory=True)
        self.note('notes/n.md', 'n', sources=['escape/secret'])
        self.assertIn('outside', self.run_cli('check')[2])

    def test_obsidian_internal_and_trash_notes_are_ignored(self):
        self.note('.trash/deleted.md', 'n', sources=['source.txt'])
        for name in ('.obsidian/plugins/example/README.md', '.knowledge/internal.md'):
            file = self.vault / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('not a vault note', encoding='utf-8')
        status, output, errors = self.run_cli('check')
        self.assertEqual(status, 0, errors)
        self.assertIn('3 notes', output)

    def test_credential_symlink_alias_is_rejected(self):
        (self.repo / '.env').write_text('secret', encoding='utf-8')
        (self.repo / 'innocent.txt').symlink_to(self.repo / '.env')
        self.note('notes/n.md', 'n', sources=['innocent.txt'])
        self.assertIn('credential source is forbidden', self.run_cli('check')[2])

    def test_output_symlinks_do_not_overwrite_canonical_note(self):
        original_script = k.__file__
        fake_script = self.root / 'skill/scripts/knowledge.py'
        fake_script.parent.mkdir(parents=True)
        (self.root / 'skill/assets').mkdir()
        (self.root / 'skill/assets/viewer.html').write_text('__KNOWLEDGE_DATA__', encoding='utf-8')
        k.__file__ = str(fake_script)
        note = self.vault / 'notes/n.md'
        original = note.read_bytes()
        try:
            for name in ('graph.html', 'Map.canvas', '.knowledge/graph.json'):
                with self.subTest(name=name):
                    output = self.vault / name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.symlink_to(note)
                    with self.assertRaisesRegex(ValueError, 'output path contains symlink'):
                        self.run_cli('build')
                    self.assertEqual(original, note.read_bytes())
                    output.unlink()
            snapshot = self.vault / '.knowledge/sources.json'
            snapshot.symlink_to(note)
            self.assertEqual(self.run_cli('snapshot', '--all')[0], 1)
            self.assertEqual(original, note.read_bytes())
            snapshot.unlink()
            (self.vault / '.knowledge').rmdir()
            (self.vault / '.knowledge').symlink_to(self.vault / 'notes', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'output path contains symlink'):
                self.run_cli('snapshot', '--all')
            self.assertEqual(original, note.read_bytes())
        finally:
            k.__file__ = original_script

    def test_strict_check_and_command_boundaries(self):
        status, _, err = self.run_cli('check', '--strict')
        self.assertEqual(status, 1)
        self.assertIn('unbaselined source', err)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.assertEqual(self.run_cli('check', '--strict')[0], 0)
        (self.repo / 'source.txt').write_text('changed', encoding='utf-8')
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 0)
        self.assertIn('changed source', err)
        status, _, err = self.run_cli('check', '--strict')
        self.assertEqual(status, 1)
        self.assertIn('changed source', err)
        for args in (('build', '--strict'), ('snapshot', '--all', '--strict'),
                     ('build', '--all'), ('build', '--notes', 'n')):
            with self.subTest(args=args), self.assertRaises(SystemExit) as exc:
                self.run_cli(*args)
            self.assertEqual(exc.exception.code, 2)

    def test_conflict_groups_block_all_commands_but_prose_is_valid(self):
        self.note('notes/n.md', 'n', sources=['source.txt'], body='> quoted\n=======\n> still quoted')
        self.assertEqual(self.run_cli('check')[0], 0)
        path = self.vault / 'notes/n.md'
        path.write_text(path.read_text().replace('status: "current"', 'status: "conflict"'))
        self.assertEqual(self.run_cli('check')[0], 0)
        for group in ('<<<<<<< ours\nleft\n=======\nright\n>>>>>>> theirs',
                      '```\n<<<<<<< ours\nleft\n||||||| base\nbase\n=======\nright\n>>>>>>> theirs\n```'):
            self.note('notes/n.md', 'n', sources=['source.txt'], body=group)
            for args in (('check',), ('snapshot', '--all'), ('build',)):
                with self.subTest(group=group, args=args):
                    status, _, err = self.run_cli(*args)
                    self.assertEqual(status, 1)
                    self.assertIn('unresolved Git conflict markers', err)
            self.assertFalse((self.vault / '.knowledge/sources.json').exists())
            self.assertFalse((self.vault / 'graph.html').exists())

    def test_real_git_conflict_with_custom_width(self):
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=check)
        # The vault is inside a disposable repository for a real Git merge.
        git('init', '-b', 'main')
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'user.name', 'Test')
        (self.root / '.gitattributes').write_text('vault/notes/n.md conflict-marker-size=5\n')
        git('add', '.')
        git('commit', '-m', 'base')
        git('checkout', '-b', 'other')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='other change')
        git('commit', '-am', 'other')
        git('checkout', 'main')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='main change')
        git('commit', '-am', 'main')
        self.assertNotEqual(git('merge', 'other', check=False).returncode, 0)
        content = (self.vault / 'notes/n.md').read_text()
        self.assertIn('<<<<< HEAD', content)
        self.assertIn('=====\n', content)
        self.assertIn('>>>>> other', content)
        for args in (('check',), ('snapshot', '--all'), ('build',)):
            with self.subTest(args=args):
                status, _, err = self.run_cli(*args)
                self.assertEqual(status, 1)
                self.assertIn('unresolved Git conflict markers', err)
        self.assertFalse((self.vault / '.knowledge/sources.json').exists())
        self.assertFalse((self.vault / 'graph.html').exists())
        self.assertFalse(k.has_conflict_markers('> quoted\n=====\n> another quote'))
        self.assertFalse(k.has_conflict_markers('<<<<< ours\n=====\n>>>>>> theirs'))

    def test_real_default_conflict_with_operator_content(self):
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=check)
        git('init', '-b', 'main')
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'user.name', 'Test')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='base side')
        git('add', '.')
        git('commit', '-m', 'base')
        git('checkout', '-b', 'other')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='<\nright side')
        git('commit', '-am', 'other')
        git('checkout', 'main')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='left side')
        git('commit', '-am', 'main')
        git('checkout', 'other')
        self.assertNotEqual(git('merge', 'main', check=False).returncode, 0)
        content = (self.vault / 'notes/n.md').read_text()
        self.assertIn('<<<<<<< HEAD\n<\nright side', content)
        self.assertTrue(k.has_conflict_markers(content))
        for args in (('check',), ('snapshot', '--all'), ('build',)):
            status, _, err = self.run_cli(*args)
            self.assertEqual(status, 1, args)
            self.assertIn('unresolved Git conflict markers', err)
        self.assertFalse(k.has_conflict_markers('```\n<\n=\n>\n```'))
        self.assertTrue(k.has_conflict_markers('<<<<<<< HEAD\n< nested\n=======\nx\n>>>>>>> main'))

    def test_snapshot_freshness_and_build(self):
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        baseline = (self.vault / '.knowledge/sources.json').read_bytes()
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.assertEqual(baseline, (self.vault / '.knowledge/sources.json').read_bytes())
        (self.repo / 'source.txt').write_text('changed', encoding='utf-8')
        self.assertIn('changed source', self.run_cli('check')[2])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='Привет </script>')
        template = Path(k.__file__).parent.parent / 'assets/viewer.html'
        # Build is tested with an isolated temporary template, never the shared asset.
        original = k.__file__
        fake_script = self.root / 'skill/scripts/knowledge.py'
        fake_script.parent.mkdir(parents=True)
        (self.root / 'skill/assets').mkdir()
        (self.root / 'skill/assets/viewer.html').write_text('<script>const x=__KNOWLEDGE_DATA__</script>', encoding='utf-8')
        k.__file__ = str(fake_script)
        try:
            self.assertEqual(self.run_cli('build')[0], 0)
        finally:
            k.__file__ = original
        self.assertEqual(baseline, (self.vault / '.knowledge/sources.json').read_bytes())
        html = (self.vault / 'graph.html').read_text(encoding='utf-8')
        self.assertIn('Привет', html)
        self.assertIn('\\u003c/script\\u003e', html)
        graph = json.loads((self.vault / '.knowledge/graph.json').read_text())
        self.assertTrue(next(n for n in graph['nodes'] if n['id'] == 'n')['stale'])


if __name__ == '__main__':
    unittest.main()
