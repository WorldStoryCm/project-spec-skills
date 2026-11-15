import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('knowledge', Path(__file__).with_name('knowledge.py'))
k = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k)


class Fixture(unittest.TestCase):
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

    def note(self, path, ident, ptype='note', areas=None, sources=None, body='', status='current', **extra):
        meta = {'id': ident, 'title': 'Тест ' + ident, 'type': ptype, 'status': status,
                'areas': ['a'] if areas is None else areas, 'sources': sources or [], 'updated': '2026-11-14'}
        if status is None:
            del meta['status']
        meta.update(extra)
        file = self.vault / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('---\n' + ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in meta.items()) + '---\n' + body, encoding='utf-8')

    def run_cli(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = k.main([*args, '--repo', str(self.repo), '--vault', str(self.vault)])
        return status, out.getvalue(), err.getvalue()


class KnowledgeTests(Fixture):
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
        path.write_text(path.read_text().replace('status: "current"', 'status: "partial"'))
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


GAP_BODY = ''.join(f'## {name}\n\ntext\n\n' for name in k.GAP_SECTIONS)


def section_body(**texts):
    return ''.join(f'## {name}\n\n{texts.get(name, "text")}\n\n' for name in k.GAP_SECTIONS)


class GapLayerTests(Fixture):
    GAP = {'kind': 'product-gap', 'recheck': 'not-checked', 'decision': 'open'}

    def gap(self, ident='g', body=GAP_BODY, **props):
        merged = {**self.GAP, **props}
        status = merged.pop('status', None)
        self.note(f'gaps/{ident}.md', ident, 'gap', body=body, status=status, **merged)

    def errors(self):
        status, _, err = self.run_cli('check')
        return status, err

    def assertInvalid(self, fragment):
        status, err = self.errors()
        self.assertEqual(status, 1, err)
        self.assertIn(fragment, err)

    def build(self):
        original = k.__file__
        fake = self.root / 'skill/scripts/knowledge.py'
        fake.parent.mkdir(parents=True, exist_ok=True)
        (self.root / 'skill/assets').mkdir(exist_ok=True)
        (self.root / 'skill/assets/viewer.html').write_text('<script>const x=__KNOWLEDGE_DATA__</script>', encoding='utf-8')
        k.__file__ = str(fake)
        try:
            return self.run_cli('build')
        finally:
            k.__file__ = original

    # status rules
    def test_status_rules_per_type(self):
        for kind, status, ok in [('note', 'current', True), ('note', 'planned', False), ('area', 'planned', False),
                                 ('note', 'unverified', False), ('note', 'conflict', False),
                                 ('run', 'planned', True), ('index', 'planned', True), ('run', 'unverified', False)]:
            with self.subTest(kind=kind, status=status):
                path = self.vault / 'notes/x.md'
                path.unlink(missing_ok=True)
                self.note('notes/x.md', 'x', kind, sources=['source.txt'], status=status,
                          areas=[] if kind in {'run', 'index'} else None)
                self.assertEqual(self.errors()[0], 0 if ok else 1, self.errors()[1])
        self.note('notes/x.md', 'x', sources=['source.txt'], status='unverified')
        self.assertInvalid('record it as a gap')

    def test_non_gap_requires_status_and_gap_forbids_it(self):
        self.note('notes/x.md', 'x', status=None)
        self.assertInvalid('missing properties: status')
        (self.vault / 'notes/x.md').unlink()
        self.gap(status='current')
        self.assertInvalid('gaps use recheck and decision')

    def test_valid_gap_and_plan_pass_strict_check(self):
        self.gap()
        self.gap('g2', recheck='confirmed', rechecked_by='agent', rechecked_on='2026-11-15', decision='accepted',
                 decided_by='Ann', decided_on='2026-11-15', priority='high', confidence='medium',
                 body=section_body(Recheck='ran it', Decision='Ann said yes'))
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='g2')
        self.run_cli('snapshot', '--all')
        status, err = self.errors()
        self.assertEqual(status, 0, err)
        self.assertEqual(self.run_cli('check', '--strict')[0], 0)

    # gap properties
    def test_gap_property_rules(self):
        cases = [
            ({'kind': 'wish'}, 'kind must be one of'),
            ({'recheck': 'maybe'}, 'recheck must be one of'),
            ({'decision': 'later'}, 'decision must be one of'),
            ({'recheck': 'confirmed'}, 'rechecked_by is required'),
            ({'recheck': 'confirmed', 'rechecked_by': 'agent'}, 'rechecked_on is required'),
            ({'recheck': 'confirmed', 'rechecked_by': ' ', 'rechecked_on': '2026-11-15'}, 'rechecked_by must name'),
            ({'recheck': 'confirmed', 'rechecked_by': 'agent', 'rechecked_on': '2026-13-45'}, 'rechecked_on'),
            ({'rechecked_by': 'Ann'}, "absent while recheck is 'not-checked'"),
            ({'rechecked_on': '2026-11-15'}, "absent while recheck is 'not-checked'"),
            ({'decision': 'accepted'}, 'decided_by is required'),
            ({'decision': 'rejected', 'decided_by': 'Ann'}, 'decided_on is required'),
            ({'decision': 'deferred', 'decided_by': 'agent', 'decided_on': '2026-11-15'}, 'agent may not decide'),
            ({'decision': 'accepted', 'decided_by': 'Ann', 'decided_on': 'yesterday'}, 'decided_on must be'),
            ({'decided_by': 'Ann'}, "absent while decision is 'open'"),
            ({'decided_on': '2026-11-15'}, "absent while decision is 'open'"),
            ({'decision': 'duplicate'}, 'duplicate_of is required'),
            ({'decision': 'duplicate', 'duplicate_of': 'g'}, 'different gap'),
            ({'decision': 'duplicate', 'duplicate_of': 'nope'}, 'not the id of an existing gap'),
            ({'decision': 'duplicate', 'duplicate_of': 'n'}, 'not the id of an existing gap'),
            ({'duplicate_of': 'other'}, "only valid when decision is 'duplicate'"),
            ({'priority': 3}, 'priority must be a string'),
        ]
        self.gap('other')
        for props, fragment in cases:
            with self.subTest(props=props):
                self.gap(**props)
                self.assertInvalid(fragment)
        (self.vault / 'gaps/g.md').unlink()
        self.assertEqual(self.errors()[0], 0)

    def test_duplicate_done_and_agent_bookkeeping_are_valid(self):
        self.gap('other')
        self.gap('g', decision='duplicate', duplicate_of='other')
        self.gap('h', decision='done', body=section_body(Decision='Closed: src/x implements it'))
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_gap_only_properties_rejected_on_other_pages(self):
        self.note('notes/x.md', 'x', sources=['source.txt'], kind='conflict')
        self.assertInvalid('kind is only valid on gap pages')
        self.note('notes/x.md', 'x', sources=['source.txt'], gap='g')
        self.assertInvalid('gap is only valid on plan pages')

    # plans
    def test_plan_rules(self):
        self.gap('open-gap')
        self.gap('ok-gap', decision='done', body=section_body(Decision='seen in code'))
        for props, fragment in [({'gap': 'open-gap'}, "has decision 'open'"), ({'gap': 'missing'}, 'not the id of an existing gap'),
                                ({'gap': 'n'}, 'not the id of an existing gap'), ({'gap': ' '}, 'plan requires gap')]:
            with self.subTest(props=props):
                self.note('plans/p.md', 'p', 'plan', status='planned', **props)
                self.assertInvalid(fragment)
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='ok-gap', areas=[])
        self.assertInvalid('plan requires an area')
        self.note('plans/p.md', 'p', 'plan', status='unverified', gap='ok-gap')
        self.assertInvalid('status must be one of')
        self.note('plans/p.md', 'p', 'plan', status='current', gap='ok-gap')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    # body rules
    def test_spec_pages_cannot_link_to_gap_layer(self):
        self.gap()
        self.note('notes/n.md', 'n', sources=['source.txt'], body='see [[gaps/g]]')
        self.assertInvalid('link from the gap to this page instead')
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.note('areas/a.md', 'a', 'area', areas=[], body='[[g]]')
        self.assertInvalid('spec pages must not link to the gap layer')
        self.note('areas/a.md', 'a', 'area', areas=[])
        self.gap(body=GAP_BODY + 'link to [[notes/n]]')
        self.note('00-index.md', 'index', 'index', areas=[], body='[[areas/a]] [[gaps/g]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_plan_link_from_note_is_rejected(self):
        self.gap(decision='accepted', decided_by='Ann', decided_on='2026-11-15', body=section_body())
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='g')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='[[plans/p]]')
        self.assertInvalid('spec pages must not link')

    def test_gap_sections(self):
        names = k.GAP_SECTIONS
        self.gap(body=''.join(f'## {n}\ntext\n' for n in names[:-1]))
        self.assertInvalid("exactly one '## Decision' section (found 0)")
        self.gap(body=GAP_BODY + '## Gap\nagain\n')
        self.assertInvalid("exactly one '## Gap' section (found 2)")
        self.gap(body=GAP_BODY.replace('## Evidence', '### Evidence'))
        self.assertInvalid("'## Evidence' section (found 0)")
        # headings in code fences do not count, and order is free
        shuffled = ''.join(f'## {n}\ntext\n' for n in reversed(names))
        self.gap(body=shuffled + '```\n## Decision\n```\n')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(body=''.join(f'## {n}\ntext\n' for n in names[:-1]) + '```\n## Decision\n```\n')
        self.assertInvalid("(found 0)")

    def test_decision_and_recheck_sections_must_not_be_empty(self):
        self.gap(decision='rejected', decided_by='Ann', decided_on='2026-11-15', body=section_body(Decision=' '))
        self.assertInvalid('Decision section must say who decided')
        self.gap(recheck='not-reproduced', rechecked_by='Ann', rechecked_on='2026-11-15', body=section_body(Recheck=''))
        self.assertInvalid('Recheck section must say what was checked')
        self.gap(body=section_body(Decision='', Recheck=''))
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(recheck='confirmed', rechecked_by='agent', rechecked_on='2026-11-15', body=section_body(Recheck='```\ncmd\n```'))
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_sources_optional_on_gap_and_plan_but_required_on_current_note(self):
        self.gap()
        self.assertEqual(self.errors()[0], 0)
        self.note('notes/x.md', 'x', sources=[])
        self.assertInvalid('current note requires sources')

    # derived state and generated files
    def test_gap_state_table(self):
        base = {'kind': 'product-gap'}
        checked = {'recheck': 'confirmed', 'rechecked_by': 'agent', 'rechecked_on': '2026-11-15'}
        self.assertEqual(k.gap_state({**base, 'recheck': 'not-checked', 'decision': 'open'}), 'needs-recheck')
        for recheck in ('confirmed', 'not-reproduced'):
            self.assertEqual(k.gap_state({**base, 'recheck': recheck, 'decision': 'open'}), 'needs-decision')
        for decision in ('accepted', 'rejected', 'deferred', 'done', 'duplicate'):
            for recheck in k.RECHECKS:
                self.assertEqual(k.gap_state({'recheck': recheck, 'decision': decision}), decision)

    def test_build_writes_all_outputs_with_new_node_fields(self):
        self.gap('open')
        self.gap('acc', recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15', decision='accepted',
                 decided_by='Ann', decided_on='2026-11-16', body=section_body())
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='acc')
        self.assertEqual(self.build()[0], 0)
        for name in ('AS-BUILT.md', 'GAPS.md', 'graph.html', 'Map.canvas', '.knowledge/graph.json'):
            self.assertTrue((self.vault / name).is_file(), name)
        nodes = {n['id']: n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        fields = {'kind', 'recheck', 'recheckedBy', 'recheckedOn', 'decision', 'decidedBy', 'decidedOn', 'state', 'gap', 'layer'}
        self.assertTrue(all(fields <= n.keys() for n in nodes.values()))
        self.assertEqual((nodes['open']['state'], nodes['open']['status'], nodes['open']['layer']), ('needs-recheck', '', 'gap'))
        self.assertEqual((nodes['acc']['state'], nodes['acc']['recheckedBy'], nodes['acc']['decidedOn']), ('accepted', 'Bob', '2026-11-16'))
        self.assertEqual((nodes['p']['gap'], nodes['p']['layer'], nodes['p']['status']), ('acc', 'gap', 'planned'))
        self.assertEqual((nodes['n']['layer'], nodes['n']['state'], nodes['n']['kind']), ('spec', '', ''))
        self.assertEqual(nodes['index']['layer'], 'nav')
        html = (self.vault / 'graph.html').read_text()
        self.assertIn('needs-recheck', html)
        canvas = json.loads((self.vault / 'Map.canvas').read_text())
        self.assertEqual({n['id'] for n in canvas['nodes']}, set(nodes))

    def test_gaps_md_groups_by_state_in_order(self):
        self.gap('b-open')
        self.gap('a-conf', recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15')
        self.gap('z-done', decision='done', body=section_body(Decision='in code'))
        self.gap('d-dup', decision='duplicate', duplicate_of='b-open')
        self.gap('acc', decision='accepted', decided_by='Ann', decided_on='2026-11-16', priority='high',
                 body=section_body(Decision='yes'))
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='acc')
        self.build()
        text = (self.vault / 'GAPS.md').read_text()
        self.assertTrue(text.startswith('> Generated by'))
        self.assertFalse(text.startswith('---'))
        heads = [line for line in text.splitlines() if line.startswith('## ')]
        self.assertEqual(heads, ['## needs-recheck', '## needs-decision', '## accepted', '## done', '## duplicate'])
        self.assertIn('| [[gaps/acc\\|Тест acc]] | product-gap | Тест a | not-checked | accepted (Ann, 2026-11-16) | high | [[plans/p\\|Тест p]] |', text)
        self.assertIn('confirmed (still holds) (Bob, 2026-11-15)', text)
        self.assertIn('duplicate of [[gaps/b-open\\|Тест b-open]]', text)
        again = text
        self.build()
        self.assertEqual(again, (self.vault / 'GAPS.md').read_text())

    def test_as_built_md_content(self):
        self.note('areas/b.md', 'b', 'area', areas=[], summary='Second area.')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='# Heading\n\nIntro [[areas/a|x]]\n\n## Rules\n\n```md\n# not a heading\n```\n\n### Deep\n#### D4\n#tag\n')
        self.note('notes/multi.md', 'multi', areas=['b', 'a'], sources=['source.txt'], body='M')
        self.note('notes/old.md', 'old', sources=['source.txt'], status='superseded')
        self.gap('g', body=GAP_BODY)
        self.build()
        text = (self.vault / 'AS-BUILT.md').read_text()
        self.assertTrue(text.startswith('> Generated by'))
        self.assertIn('# Тест index: as-built specification', text)
        self.assertLess(text.index('## Тест a'), text.index('## Тест b'))
        self.assertIn('Second area.', text)
        self.assertIn('### Тест n\n\n**id:** `n` · **status:** current · **updated:** 2026-11-14 · **sources:** `source.txt`', text)
        self.assertNotIn('\n# Heading', text)
        self.assertIn('\n#### Rules\n', text)
        self.assertIn('\n##### Deep\n', text)
        self.assertIn('\n###### D4\n', text)
        self.assertIn('\n#tag', text)
        self.assertIn('```md\n# not a heading\n```', text)
        self.assertIn('Intro [[areas/a|x]]', text)
        self.assertIn('- See also [[notes/multi|Тест multi]] (described under Тест b)', text)
        self.assertNotIn('Тест old', text)
        self.assertNotIn('Тест g', text)
        self.assertEqual(text.count('### Тест multi'), 1)
        self.build()
        self.assertEqual(text, (self.vault / 'AS-BUILT.md').read_text())

    def test_as_built_rebases_relative_markdown_links(self):
        self.note('notes/n.md', 'n', sources=['source.txt'], body='[s](../../src/x.py#L3) [w](https://e.x/a) [a](#top) ![i](<../img a.png>) [root](/abs)\n\n[ref]: ../r.md\n\n```\n[c](../keep.md)\n```\n')
        self.build()
        text = (self.vault / 'AS-BUILT.md').read_text()
        self.assertIn('[s](../src/x.py#L3) [w](https://e.x/a) [a](#top) ![i](<img a.png>) [root](/abs)', text)
        self.assertIn('[ref]: r.md', text)
        self.assertIn('[c](../keep.md)', text)

    def test_generated_files_are_reserved_names(self):
        (self.vault / 'AS-BUILT.md').write_text(k.GENERATED + '\n\n# No frontmatter\n[[nowhere]]')
        (self.vault / 'GAPS.md').write_text(k.GENERATED + '\nno frontmatter either')
        (self.vault / 'sub').mkdir()
        (self.vault / 'sub/GAPS.md').write_text('---\nbroken')
        status, err = self.errors()
        self.assertEqual(status, 1)
        self.assertNotIn('AS-BUILT.md', err)
        self.assertNotIn('error: GAPS.md', err)
        self.assertIn('sub/GAPS.md', err)  # only the root names are reserved
        (self.vault / 'sub/GAPS.md').unlink()
        self.assertEqual(self.errors()[0], 0)
        self.assertIn('3 notes', self.run_cli('check')[1])

    def test_symlinked_generated_file_is_refused(self):
        (self.vault / 'GAPS.md').symlink_to(self.vault / 'notes/n.md')
        original = (self.vault / 'notes/n.md').read_bytes()
        self.assertEqual(self.build()[0], 1)  # a link to a hand-written page is not a generated file
        self.assertEqual(original, (self.vault / 'notes/n.md').read_bytes())

    # defects
    def test_fence_detection_follows_commonmark(self):
        bad = '[[missing]]'
        for body in (f'```npm test``` passed.\n{bad}', f'```\ncode\n```js\n{bad}\n```\n{bad}', f'~~~\n~~~ x\n{bad}\n~~~\n{bad}'):
            with self.subTest(body=body):
                self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
                self.assertInvalid('missing wikilink missing')
        for body in (f'```js\n{bad}\n```', f'~~~ weird `x`\n{bad}\n~~~', f'````\n```\n{bad}\n````', f'```\n{bad}'):
            with self.subTest(body=body):
                self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
                self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.assertEqual(k.prose('```npm test``` passed. [[a]]'), ' passed. [[a]]')

    def test_escaped_pipe_wikilink_in_table(self):
        self.note('notes/n.md', 'n', sources=['source.txt'], body='| a |\n| - |\n| [[areas/a\\|Alias]] |\n| [[a\\|Alias]] [[a|B]] [[a\\|x]] |')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='| [[nope\\|Alias]] |')
        self.assertInvalid('missing wikilink nope')

    def test_utf8_bom_is_accepted(self):
        file = self.vault / 'notes/n.md'
        file.write_bytes(b'\xef\xbb\xbf' + file.read_bytes())
        status, err = self.errors()
        self.assertEqual(status, 0, err)

    def test_credential_denylist(self):
        for name in ('.npmrc', '.netrc', '.htpasswd', 'id_rsa', 'id_ed25519', 'id_ecdsa', 'x/terraform.tfstate',
                     'terraform.tfstate.backup', 'service-account.json', 'service-account-prod.json', 'deep/dir/.NPMRC'):
            with self.subTest(name=name):
                self.assertTrue(k.credential_path(name))
        for name in ('id_rsa.pub', 'id_ed25519.pub', 'service-accounts.md', 'service_account.py', 'npmrc.md', 'src/service-account.ts'):
            with self.subTest(name=name):
                self.assertFalse(k.credential_path(name))
        (self.repo / '.npmrc').write_text('//registry:_authToken=x')
        self.note('notes/n.md', 'n', sources=['.npmrc'])
        self.assertInvalid('credential source is forbidden')

    def test_crlf_only_difference_is_reported_as_line_endings(self):
        source = self.repo / 'source.txt'
        source.write_bytes(b'one\ntwo\n')
        self.run_cli('snapshot', '--all')
        source.write_bytes(b'one\r\ntwo\r\n')
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 0)
        self.assertIn('line endings differ in source source.txt', err)
        self.assertNotIn('changed source', err)
        self.assertEqual(self.run_cli('check', '--strict')[0], 1)
        source.write_bytes(b'one\r\nthree\r\n')
        self.assertIn('changed source', self.run_cli('check')[2])
        # and the reverse direction
        source.write_bytes(b'one\r\ntwo\r\n')
        self.run_cli('snapshot', '--all')
        source.write_bytes(b'one\ntwo\n')
        self.assertIn('line endings differ', self.run_cli('check')[2])

    def test_generated_writes_are_atomic(self):
        self.run_cli('snapshot', '--all')
        snapshot = self.vault / '.knowledge/sources.json'
        before = snapshot.read_bytes()
        real = k.os.replace
        calls = []

        def failing(src, dst):
            calls.append(dst)
            raise OSError('disk full')
        k.os.replace = failing
        try:
            (self.repo / 'source2.txt').write_text('x')
            self.note('notes/m.md', 'm', sources=['source2.txt'])
            with self.assertRaises(OSError):
                self.run_cli('snapshot', '--all')
        finally:
            k.os.replace = real
        self.assertTrue(calls)
        self.assertEqual(before, snapshot.read_bytes())
        self.assertEqual([p.name for p in snapshot.parent.iterdir()], ['sources.json'])
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.assertEqual([p.name for p in snapshot.parent.iterdir()], ['sources.json'])
        self.assertEqual(oct(snapshot.stat().st_mode & 0o777), oct(0o666 & ~self.umask()))

    def test_missing_source_severity_follows_gap_decision(self):
        live = [{}, {'decision': 'accepted', 'decided_by': 'Ann', 'decided_on': '2026-11-15'},
                {'decision': 'deferred', 'decided_by': 'Ann', 'decided_on': '2026-11-15'}]
        closed = [{'decision': 'done'}, {'decision': 'rejected', 'decided_by': 'Ann', 'decided_on': '2026-11-15'},
                  {'decision': 'duplicate', 'duplicate_of': 'other'}]
        self.gap('other')
        for props in live + closed:
            with self.subTest(props=props):
                self.gap('g', sources=['gone.txt'], body=section_body(), **props)
                status, err = self.errors()
                if props in live:
                    self.assertEqual(status, 1)
                    self.assertIn('missing or not a file', err)
                else:
                    self.assertEqual(status, 0, err)
                    self.assertIn('WARNING: gaps/g.md: missing source gone.txt', err)
        (self.vault / 'gaps/g.md').unlink()
        self.gap('done', decision='done', body=section_body())
        self.gap('acc', decision='accepted', decided_by='Ann', decided_on='2026-11-15', body=section_body())
        self.note('plans/p1.md', 'p1', 'plan', status='planned', gap='done', sources=['gone.txt'])
        status, err = self.errors()
        self.assertEqual(status, 0, err)
        self.assertIn('plans/p1.md: missing source gone.txt', err)
        self.note('plans/p2.md', 'p2', 'plan', status='planned', gap='acc', sources=['gone.txt'])
        self.assertInvalid('p2.md: gone.txt: source is missing')

    def test_edges_include_gap_and_plan_links_and_plan_gap(self):
        self.gap('g', decision='accepted', decided_by='Ann', decided_on='2026-11-15', body=section_body() + '[[notes/n]]')
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='g', body='nothing linked')
        self.build()
        graph = json.loads((self.vault / '.knowledge/graph.json').read_text())
        edges = {(e['source'], e['target']) for e in graph['edges']}
        self.assertIn(('g', 'n'), edges)
        self.assertIn(('p', 'g'), edges)

    def test_priority_confidence_duplicate_of_nodes_and_recheck_staleness(self):
        self.gap('other')
        self.gap('dup', decision='duplicate', duplicate_of='other')
        self.gap('c', recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15', priority='high',
                 confidence='low', sources=['source.txt'], body=section_body())
        self.gap('nc', sources=['source.txt'])
        self.run_cli('snapshot', '--all')
        self.build()
        nodes = {n['id']: n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        self.assertEqual((nodes['c']['priority'], nodes['c']['confidence'], nodes['c']['duplicateOf']), ('high', 'low', ''))
        self.assertEqual((nodes['dup']['duplicateOf'], nodes['n']['priority'], nodes['n']['duplicateOf']), ('other', '', ''))
        self.assertNotIn('sources changed since', (self.vault / 'GAPS.md').read_text())
        (self.repo / 'source.txt').write_text('different')
        self.build()
        first = (self.vault / 'GAPS.md').read_text()
        row = lambda ident: next(l for l in first.splitlines() if l.startswith(f'| [[gaps/{ident}\\|'))
        self.assertIn('confirmed (still holds) (Bob, 2026-11-15) · sources changed since', row('c'))
        self.assertNotIn('changed since', row('nc'))  # never rechecked: nothing to flag
        self.build()
        self.assertEqual(first, (self.vault / 'GAPS.md').read_text())
        # stored fields are never rewritten
        self.assertIn('recheck: "confirmed"', (self.vault / 'gaps/c.md').read_text())

    # review round 1
    def test_embeds_are_resolved_and_cannot_reach_the_gap_layer(self):
        self.gap(decision='done', body=section_body())
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[gaps/g]]')
        self.assertInvalid('spec pages must not link to the gap layer (embed gaps/g)')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[nowhere]]')
        self.assertInvalid('missing embed nowhere')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[pic.png]]')
        self.assertInvalid('missing embed pic.png')
        (self.vault / 'attachments').mkdir()
        (self.vault / 'attachments/pic.png').write_bytes(b'png')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[areas/a]] ![[a#x|alias]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_markdown_links_to_the_gap_layer_are_rejected_from_spec_pages(self):
        self.gap(decision='done', body=section_body())
        for body in ('[x](../gaps/g.md)', '[x](<../gaps/g.md#top>)', '[x](../gaps/%67.md)', '[queue](../GAPS.md)',
                     '[queue](../gaps.md)', '[x]: ../gaps/g.md'):
            with self.subTest(body=body):
                self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
                self.assertInvalid('spec pages must not link to the gap layer')
        self.note('areas/a.md', 'a', 'area', areas=[], body='[x](../gaps/g.md)')
        self.assertInvalid('spec pages must not link to the gap layer')
        self.note('areas/a.md', 'a', 'area', areas=[])
        for body in ('[ok](../source.txt) [web](https://example.invalid/gaps/g.md) `[c](../gaps/g.md)`', '```\n[c](../gaps/g.md)\n```'):
            self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
            self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(body=section_body() + '[n](../notes/n.md)', decision='done')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_links_in_title_or_summary_of_spec_pages_are_rejected(self):
        for key, value in (('title', 'See [[gaps/g]]'), ('summary', 'See [q](GAPS.md)'), ('summary', '![[gaps/g]]')):
            with self.subTest(key=key):
                self.note('notes/n.md', 'n', sources=['source.txt'], **{key: value})
                self.assertInvalid(f'{key} of a spec page must not contain links')
        self.note('areas/a.md', 'a', 'area', areas=[], summary='[[g]]')
        self.assertInvalid('summary of a spec page must not contain links')
        self.note('areas/a.md', 'a', 'area', areas=[], summary='Plain [brackets] and (parens).')
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_control_characters_in_properties_are_rejected(self):
        for char in ('\r', '\n', '\t', '\x00', '\x7f', '\x85', ' ', ' '):
            for key, value in (('title', 'a' + char + 'b'), ('summary', 'a' + char + 'b'), ('tags', ['x' + char]), ('sources', ['source.txt' + char])):
                with self.subTest(char=repr(char), key=key):
                    self.note('notes/n.md', 'n', **{key: value, **({} if key == 'sources' else {'sources': ['source.txt']})})
                    # Raw U+0085/U+2028/U+2029 break the one-property-per-line frontmatter before validation.
                    self.assertInvalid('ERROR: notes/n.md')
        for char in ('\\u0085', '\\u2028', '\\u2029'):  # JSON escapes survive line splitting, so validation must catch them
            self.note('notes/n.md', 'n', sources=['source.txt'])
            path = self.vault / 'notes/n.md'
            path.write_text(path.read_text().replace('title: "Тест n"', 'title: "a' + char + 'b"'))
            self.assertInvalid('title must not contain control characters')
        self.gap(rechecked_by='agent, 2026-11-15)\r\r## accepted', recheck='confirmed', rechecked_on='2026-11-15', body=section_body())
        self.assertInvalid('rechecked_by must not contain control characters')

    def test_generated_markdown_neutralises_property_values(self):
        title = 'Evil <!-- | \\ `x` --> <b>'
        self.gap('g', recheck='confirmed', rechecked_by='Ann <!--', rechecked_on='2026-11-15', priority='-->  |  hi',
                 decision='accepted', decided_by='Bo\\', decided_on='2026-11-15', body=section_body())
        text = (self.vault / 'gaps/g.md').read_text().replace('title: "Тест g"', 'title: ' + json.dumps(title))
        (self.vault / 'gaps/g.md').write_text(text)
        self.note('areas/a.md', 'a', 'area', areas=[], summary='## forged heading')
        self.note('notes/n.md', 'n', sources=['source.txt'], title='## <script>')
        self.assertEqual(self.build()[0], 0)
        gaps = (self.vault / 'GAPS.md').read_text()
        row = next(l for l in gaps.splitlines() if l.startswith('| [[gaps/g'))
        self.assertNotIn('<', row)
        self.assertIn('Ann &lt;!--', row)
        self.assertIn('Bo\\\\', row)
        self.assertIn('--> \\|', row)  # the pipe inside priority stays inside its cell
        cells = [c for c in re.split(r'(?<!\\)\|', row) if c.strip()]
        self.assertEqual(len(cells), 7, row)
        self.assertEqual(sum(1 for l in gaps.splitlines() if l.startswith('## ')), 1)
        built = (self.vault / 'AS-BUILT.md').read_text()
        self.assertNotIn('<script>', built)
        self.assertIn('### ## &lt;script>', built)
        self.assertNotIn('\n## forged heading', built)
        self.assertIn('\\## forged heading', built)

    def test_reserved_generated_names_are_case_insensitive(self):
        (self.vault / 'gaps.md').write_text('---\nid: "x"\n---\nprecious')
        status, err = self.errors()
        self.assertEqual(status, 1)
        self.assertIn('gaps.md: this name is reserved for a generated file', err)
        before = (self.vault / 'gaps.md').read_bytes()
        self.assertEqual(self.build()[0], 1)
        self.assertEqual(before, (self.vault / 'gaps.md').read_bytes())
        (self.vault / 'gaps.md').unlink()
        (self.vault / 'As-Built.md').write_text('x')
        self.assertIn('As-Built.md: this name is reserved', self.errors()[1])
        (self.vault / 'As-Built.md').unlink()
        (self.vault / 'sub').mkdir()
        (self.vault / 'sub/gaps.md').write_text('---\nid: "gs"\ntitle: "t"\ntype: "run"\nstatus: "current"\nareas: []\nsources: []\nupdated: "2026-11-15"\n---\n')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_outdated_recheck(self):
        for props, fragment in (({'recheck': 'outdated'}, 'rechecked_by is required'),
                                ({'recheck': 'outdated', 'rechecked_by': 'agent', 'rechecked_on': '2026-11-15'}, None)):
            with self.subTest(props=props):
                self.gap(body=section_body(), **props)
                if fragment:
                    self.assertInvalid(fragment)
                else:
                    self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(recheck='outdated', rechecked_by='agent', rechecked_on='2026-11-15', body=section_body(Recheck=' '))
        self.assertInvalid('Recheck section must say what was checked')
        self.assertEqual(k.gap_state({'decision': 'open', 'recheck': 'outdated'}), 'needs-recheck')
        self.assertEqual(k.gap_state({'decision': 'accepted', 'recheck': 'outdated'}), 'accepted')
        self.gap(recheck='outdated', rechecked_by='Bob', rechecked_on='2026-11-15', body=section_body(), sources=['source.txt'])
        self.build()
        node = next(n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes'] if n['id'] == 'g')
        self.assertEqual((node['state'], node['recheckOutdated']), ('needs-recheck', True))
        gaps = (self.vault / 'GAPS.md').read_text()
        self.assertIn('## needs-recheck', gaps)
        self.assertIn('outdated (Bob, 2026-11-15) |', gaps)
        self.assertNotIn('sources changed since', gaps)

    def test_recheck_outdated_flag_ignores_line_endings_and_non_gaps(self):
        source = self.repo / 'source.txt'
        source.write_bytes(b'a\nb\n')
        self.gap(recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15', body=section_body(), sources=['source.txt'])
        self.run_cli('snapshot', '--all')
        flags = lambda: {n['id']: n['recheckOutdated'] for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        self.build()
        self.assertEqual(set(flags().values()), {False})
        source.write_bytes(b'a\r\nb\r\n')
        self.build()
        self.assertFalse(flags()['g'])
        self.assertNotIn('sources changed since', (self.vault / 'GAPS.md').read_text())
        source.write_bytes(b'different')
        self.build()
        self.assertTrue(flags()['g'])
        self.assertFalse(flags()['n'])
        self.assertIn('sources changed since', (self.vault / 'GAPS.md').read_text())

    def test_setext_headings_are_demoted_in_as_built(self):
        body = 'Title\n=====\n\nIntro line\nsecond line\n-----\n\nPara\n\n---\n\n- item\n---\n\n```\nCode\n=====\n```\n\n    indented\n    ====\n'
        self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
        self.build()
        text = (self.vault / 'AS-BUILT.md').read_text()
        self.assertNotIn('\nTitle\n', text)  # leading H1 dropped like an ATX title
        self.assertIn('\n#### Intro line second line\n', text)
        self.assertIn('Para\n\n---\n', text)  # thematic break after a blank line stays
        self.assertIn('- item\n---', text)
        self.assertIn('```\nCode\n=====\n```', text)
        self.assertNotIn('=====\n\nIntro', text)
        self.note('notes/n.md', 'n', sources=['source.txt'], body='Intro\n\nSub title\n=======\ntext')
        self.build()
        self.assertIn('\n#### Sub title\n', (self.vault / 'AS-BUILT.md').read_text())

    def test_priority_and_confidence_only_on_gaps_and_plans(self):
        for key in ('priority', 'confidence'):
            with self.subTest(key=key):
                self.note('notes/n.md', 'n', sources=['source.txt'], **{key: 'high'})
                self.assertInvalid(f'{key} is only valid on gap and plan pages')
                self.note('areas/a.md', 'a', 'area', areas=[], **{key: 'high'})
                self.assertInvalid(f'{key} is only valid on gap and plan pages')
                self.note('areas/a.md', 'a', 'area', areas=[])
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.gap('done-gap', decision='done', body=section_body())
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='done-gap', priority='high', confidence='low')
        self.gap('g2', priority='high', confidence='low')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_credential_denylist_folds_lookalikes_and_covers_more_names(self):
        for name in ('.ſſh/id_rſa', '.SSH/id_rsa', 'a/.git/config', '.git', '.git-credentials', 'credentials.json',
                     'client_secret_123.json', 'secrets.yaml', 'secrets.json', '.envrc', '.pgpass', '.pypirc', '_netrc',
                     '.vault-token', '.terraformrc', '.kube/config', 'home/.docker/config.json',
                     'application_default_credentials.json', 'id_dsa', 'x.jks', 'x.ppk', 'x.p8', 'prod.tfvars', 'a.auto.tfvars', 'x.gpg'):
            with self.subTest(name=name):
                self.assertTrue(k.credential_path(name))
        for name in ('config', '.kube/other', 'docker/config.json', 'secret.md', 'credentials.md', 'src/.github/x.yml', 'client.json'):
            with self.subTest(name=name):
                self.assertFalse(k.credential_path(name))
        (self.repo / '.ssh').mkdir()
        (self.repo / '.ssh/id_rsa').write_text('private')
        self.note('notes/n.md', 'n', sources=['.ſſh/id_rſa'])
        self.assertInvalid('credential source is forbidden')
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 1)
        self.assertFalse((self.vault / '.knowledge/sources.json').exists())

    def test_rebased_link_that_would_become_a_url_scheme_is_left_alone(self):
        self.note('notes/n.md', 'n', sources=['source.txt'], body='[x](../javascript:alert(1)) [y](../data:text/html,hi) [z](../ok.txt)')
        self.build()
        text = (self.vault / 'AS-BUILT.md').read_text()
        self.assertIn('[x](../javascript:alert(1))', text)
        self.assertIn('[y](../data:text/html,hi)', text)
        self.assertIn('[z](ok.txt)', text)

    # review round 2
    def test_handwritten_page_named_like_a_generated_file_is_never_overwritten(self):
        for name in ('GAPS.md', 'AS-BUILT.md'):
            with self.subTest(name=name):
                page = self.vault / name
                page.write_text('---\nid: "mine"\ntitle: "Mine"\ntype: "index"\nstatus: "current"\nareas: []\nsources: []\nupdated: "2026-11-15"\n---\nprecious')
                before = page.read_bytes()
                status, err = self.errors()
                self.assertEqual(status, 1, err)
                self.assertIn(f'{name}: this name is reserved for a generated file', err)
                self.assertEqual(self.build()[0], 1)
                self.assertEqual(before, page.read_bytes())
                page.unlink()
        # a real generated file (banner on the first line) is skipped, and a rebuild replaces it
        self.assertEqual(self.build()[0], 0)
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.assertEqual(self.build()[0], 0)

    def test_setext_underline_applies_only_to_plain_paragraph_text(self):
        keep = ['| a | b |\n| - | - |\n| 1 | 2 |\n---\nafter', '| a |\n=====\nrest', 'a | b\n---\nx', '> quote\n---\nx',
                '[r]: http://x\n---\nx', '<div>\n---\nx', '- item\n===\nx', '* * *\n---\nx', '1. item\n---\nx']
        for body in keep:
            with self.subTest(body=body):
                self.assertEqual(k.demote(body), body)
        self.assertEqual(k.demote('---\nfoo: bar\n---\ntext'), '---\n#### foo: bar\ntext')
        self.assertEqual(k.demote('Title\n=====\nrest'), 'rest')
        self.assertEqual(k.demote('a\nb\n---\nc'), '#### a b\nc')

    def test_embed_of_a_dotted_note_name_resolves_as_a_note(self):
        self.note('notes/v1.2-rule.md', 'dotted', sources=['source.txt'])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[notes/v1.2-rule]] ![[v1.2-rule]] [[notes/v1.2-rule]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[notes/v9.9-missing]]')
        self.assertInvalid('missing embed notes/v9.9-missing')
        (self.vault / 'pic.v2.png').write_bytes(b'x')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[pic.v2.png]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_unclosed_fence_or_comment_cannot_swallow_the_rest_of_as_built(self):
        self.note('notes/a-first.md', 'first', sources=['source.txt'], body='text\n```\ncode never closed')
        self.note('notes/b-second.md', 'second', sources=['source.txt'], body='before <!-- opened but not closed\nmore')
        self.note('notes/c-third.md', 'third', sources=['source.txt'], body='ok <!-- closed --> and `<!--` in code\n\n```\n<!-- in fence\n```\n')
        self.build()
        text = (self.vault / 'AS-BUILT.md').read_text()
        first = text[text.index('### Тест first'):text.index('### Тест n\n')]
        self.assertTrue(first.rstrip().endswith('```'), first)
        self.assertEqual(first.count('```'), 2, repr(first))
        second = text[text.index('### Тест second'):text.index('### Тест third')]
        self.assertIn('&lt;!-- opened but not closed', second)
        self.assertNotIn('<!--', second)
        third = text[text.index('### Тест third'):]
        self.assertIn('ok <!-- closed --> and `<!--` in code', third)
        self.assertIn('<!-- in fence', third)
        self.assertNotIn('&lt;', third)
        # tilde fences and longer fences are closed with a matching marker
        self.assertEqual(k.demote('~~~~ js\nx'), '~~~~ js\nx\n~~~~')
        self.assertEqual(k.demote('<!-- a --> <!-- b'), '<!-- a --> &lt;!-- b')

    def test_rebased_target_that_reads_as_unc_or_protocol_relative_is_left_alone(self):
        for target in ('../\\evil.example/x', '..//\\evil.example/x', '../\\/evil.example/x', '<../\\evil.example/x>'):
            with self.subTest(target=target):
                self.assertEqual(k.rebase_target(target, 'notes'), target)
        self.assertEqual(k.rebase_target('../ok.txt', 'notes'), 'ok.txt')

    def test_wikilink_pattern_is_linear_on_unbalanced_brackets(self):
        import time
        started = time.perf_counter()
        self.assertEqual(k.LINK.findall('[[' * 20000), [])
        self.assertEqual(k.LINK.findall('![[x]] [[y|z]] [[a]]'), [('!', 'x'), ('', 'y|z'), ('', 'a')])
        self.assertLess(time.perf_counter() - started, 1.0)

    # first real sync: recheck wording, cascading errors, dirty sources, partial snapshots
    def test_gaps_md_prints_recheck_meaning_but_stores_the_value(self):
        self.gap('c', recheck='confirmed', rechecked_by='agent', rechecked_on='2026-11-15')
        self.gap('r', recheck='not-reproduced', rechecked_by='Ann', rechecked_on='2026-11-16', decision='done',
                 body=section_body(Decision='in code'))
        self.gap('o', recheck='outdated', rechecked_by='Bob', rechecked_on='2026-11-14')
        self.build()
        text = (self.vault / 'GAPS.md').read_text()
        self.assertIn('| confirmed (still holds) (agent, 2026-11-15) |', text)
        self.assertIn('| not reproduced (no longer holds) (Ann, 2026-11-16) |', text)
        self.assertIn('| outdated (Bob, 2026-11-14) |', text)
        nodes = {n['id']: n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        self.assertEqual((nodes['c']['recheck'], nodes['r']['recheck']), ('confirmed', 'not-reproduced'))

    def test_failed_page_is_a_link_target_and_causes_no_follow_on_errors(self):
        # One broken page of each kind: a note, an area (by id), a gap (by id).
        self.note('notes/broken.md', 'broken', status=None)
        self.note('areas/ba.md', 'ba', 'area', areas=[], updated='2026-13-45')
        self.gap('fg', recheck='bogus')
        self.gap('dup', decision='duplicate', duplicate_of='fg')
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='fg')
        self.note('notes/m.md', 'm', areas=['a', 'ba'], sources=['source.txt'],
                  body='[[broken]] [[notes/broken]] ![[broken]] [[nowhere]]')
        status, err = self.errors()
        self.assertEqual(status, 1, err)
        errors = [line for line in err.splitlines() if line.startswith('ERROR:')]
        self.assertEqual(len(errors), 4, err)  # three broken pages plus the one genuinely missing link
        self.assertIn('notes/m.md: missing wikilink nowhere', err)
        for noise in ('missing wikilink broken', 'missing embed broken', 'unknown area', 'is not the id of an existing gap', 'has decision'):
            self.assertNotIn(noise, err)
        self.assertIn('check: failed, 4 errors on 4 pages', err)

    def test_snapshot_notes_needs_only_the_selected_pages_valid(self):
        self.note('notes/broken.md', 'broken', status=None)
        self.note('notes/m.md', 'm', sources=['source.txt'], body='[[broken]]')
        self.assertEqual(self.run_cli('check')[0], 1)
        status, out, err = self.run_cli('snapshot', '--notes', 'n', 'm')
        self.assertEqual(status, 0, err)
        self.assertIn('1 errors on 1 other pages do not block this snapshot', err)
        baseline = json.loads((self.vault / '.knowledge/sources.json').read_text())
        self.assertEqual(sorted(baseline), ['m', 'n'])
        # The selected page itself must be valid, including one whose own frontmatter fails.
        before = (self.vault / '.knowledge/sources.json').read_bytes()
        self.note('notes/m.md', 'm', sources=['source.txt'], body='[[nowhere]]')
        self.assertEqual(self.run_cli('snapshot', '--notes', 'm')[0], 1)
        self.assertEqual(self.run_cli('snapshot', '--notes', 'broken')[0], 1)
        self.assertEqual(self.run_cli('snapshot', '--notes', 'absent')[0], 1)
        self.assertEqual(before, (self.vault / '.knowledge/sources.json').read_bytes())
        # Whole-vault commands still demand a fully valid vault.
        self.note('notes/m.md', 'm', sources=['source.txt'])
        for args in (('snapshot', '--all'), ('build',)):
            self.assertEqual(self.run_cli(*args)[0], 1, args)
        # A damaged baseline is vault-wide, so it blocks even a partial snapshot.
        (self.vault / 'notes/broken.md').unlink()
        (self.vault / '.knowledge/sources.json').write_text('[]')
        self.assertEqual(self.run_cli('snapshot', '--notes', 'n')[0], 1)

    def git_in(self, top, *args):
        return subprocess.run(['git', '-C', str(top), *args], capture_output=True, text=True, check=True).stdout

    def init_git(self, top):
        self.git_in(top, 'init', '-b', 'main')
        self.git_in(top, 'config', 'user.email', 'test@example.invalid')
        self.git_in(top, 'config', 'user.name', 'Test')
        self.git_in(top, 'add', '.')
        self.git_in(top, 'commit', '-m', 'base')

    def test_ignore_dirty_forgives_only_uncommitted_changes(self):
        self.init_git(self.repo)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        (self.repo / 'source.txt').write_text('edited', encoding='utf-8')
        status, _, err = self.run_cli('check', '--strict')
        self.assertEqual(status, 1)
        self.assertNotIn('not counted', err)
        status, out, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 0, err)
        self.assertIn('WARNING: notes/n.md: changed source source.txt (uncommitted change, not counted)', err)
        self.assertIn('(1 uncommitted, not counted)', out)
        self.git_in(self.repo, 'add', 'source.txt')  # staged still counts as uncommitted
        self.assertEqual(self.run_cli('check', '--strict', '--ignore-dirty')[0], 0)
        self.git_in(self.repo, 'commit', '-m', 'edit')  # committed changes are real
        status, _, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 1)
        self.assertIn('changed source source.txt\n', err + '\n')
        self.assertNotIn('not counted', err)
        # Untracked sources and a repo that is a subdirectory of the work tree.
        (self.repo / 'new.txt').write_text('one', encoding='utf-8')
        self.note('notes/u.md', 'u', sources=['new.txt'])
        self.assertEqual(self.run_cli('snapshot', '--notes', 'u')[0], 0)
        (self.repo / 'new.txt').write_text('two', encoding='utf-8')
        self.assertEqual(self.run_cli('check', '--strict', '--ignore-dirty')[0], 1)  # n is still committed-changed
        self.assertIn('changed source new.txt (uncommitted change, not counted)', self.run_cli('check', '--ignore-dirty')[2])

    def test_ignore_dirty_in_a_subdirectory_of_the_work_tree_and_outside_git(self):
        with self.assertRaises(SystemExit) as exc, redirect_stderr(StringIO()):
            self.run_cli('check', '--ignore-dirty')
        self.assertEqual(exc.exception.code, 2)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.init_git(self.root)
        (self.repo / 'source.txt').write_text('edited', encoding='utf-8')
        status, _, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 0, err)
        self.assertIn('(uncommitted change, not counted)', err)
        for args in (('build', '--ignore-dirty'), ('snapshot', '--all', '--ignore-dirty')):
            with self.subTest(args=args), self.assertRaises(SystemExit) as exc, redirect_stderr(StringIO()):
                self.run_cli(*args)
            self.assertEqual(exc.exception.code, 2)

    @staticmethod
    def umask():
        mask = k.os.umask(0)
        k.os.umask(mask)
        return mask


if __name__ == '__main__':
    unittest.main()
