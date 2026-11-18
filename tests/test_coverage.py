import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'skills/project-knowledge/scripts'))
import coverage as c  # noqa: E402


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve() / 'repo'
        self.vault = self.repo / 'knowledge/demo'
        (self.vault / 'notes').mkdir(parents=True)
        (self.vault / 'areas').mkdir()
        self.page('00-index.md', 'index', 'index', areas=[], body='[[areas/chat]]')
        self.page('areas/chat.md', 'chat', 'area', areas=[], body='[[notes/chats]]')
        self.page('notes/chats.md', 'chats', sources=['src/chat/send.ts'],
                  body='A message is refused with "Message can’t be empty". At most 10 photos (`CHAT_MAX_MEDIA`).\n\n'
                       '| ID | Rule |\n| --- | --- |\n| BR-CHAT-01 | Only group chats can be renamed, by a member \\| staff. |')
        self.code('src/chat/send.ts', '''
            export const CHAT_MAX_MEDIA = 10;
            export const COLD_OUTREACH_PER_HOUR: number = 5; // new people
            const RETRY_MS = 60 * 1000
            const queryKey = "chats.list";
            throw new Error("Message can't be empty");
            throw new Error('Only group chats can be renamed');
            throw new Error("You cannot remove yourself");
            console.error("Failed to load the chat list");
            const cls = "flex items-center gap-2 Text here";
            const sql = "SELECT id FROM chats WHERE owner = 1";
        ''')
        self.code('src/chat/window/Header.tsx', '<Button>Back to chat list</Button>\n<p>{count} unread</p>\nconst t = `Hello ${name}, welcome back`;')
        self.code('src/chat/window/deep/Picker.tsx', 'const label = "Smileys and people";')
        self.code('src/chat/send.test.ts', 'it("says this in a test only", () => {})')
        self.code('src/chat/__tests__/more.ts', 'const s = "Only in a test folder";')
        self.code('src/orders/pay.py', 'MAX_TOTAL = 5000\nmessage = "The order was already paid"\n')
        self.code('database/migrations/001.sql', "INSERT INTO t VALUES ('A sentence in a migration');")
        self.code('node_modules/x/index.js', 'const s = "A sentence in a dependency";')
        self.code('src/help/article.ts', '\n'.join(f'const p{i} = "This is paragraph number {i} of an article";' for i in range(45)))
        (self.repo / 'README.md').write_text('Not code. "A sentence in the readme file"', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def page(self, path, ident, ptype='note', areas=None, sources=None, body=''):
        meta = {'id': ident, 'title': 'Page ' + ident, 'type': ptype, 'status': 'current', 'areas': ['chat'] if areas is None else areas,
                'sources': sources or [], 'updated': '2026-11-18'}
        (self.vault / path).write_text('---\n' + ''.join(f'{key}: {json.dumps(value)}\n' for key, value in meta.items()) + '---\n' + body, encoding='utf-8')

    def code(self, path, text):
        file = self.repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8')

    def run_cli(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = c.main(['--repo', str(self.repo), *args])
        return status, out.getvalue(), err.getvalue()

    def measured(self, *prefixes):
        import knowledge
        notes = knowledge.load_vault(self.repo, self.vault, freshness=False, absent=[])[0]
        return c.measure(self.repo, self.vault, notes, prefixes)

    def test_reads_only_the_application_code(self):
        self.assertEqual(sorted(self.measured()), ['src/chat/send.ts', 'src/chat/window/Header.tsx', 'src/chat/window/deep/Picker.tsx',
                                                   'src/help/article.ts', 'src/orders/pay.py'])
        # with Git, an ignored folder is left out as well, and an untracked file is still read
        subprocess.run(['git', '-C', str(self.repo), 'init', '-q'], check=True)
        (self.repo / '.gitignore').write_text('src/orders/\n', encoding='utf-8')
        self.assertNotIn('src/orders/pay.py', self.measured())
        self.assertIn('src/chat/send.ts', self.measured())

    def test_finds_the_sentences_and_numbers_no_page_mentions(self):
        files = self.measured()
        send = files['src/chat/send.ts']
        self.assertEqual((send['cited'], send['sentences'], send['limits']), (True, 3, 3))
        self.assertEqual(send['unquoted'], ['You cannot remove yourself'], 'a curly apostrophe and a table row still match; logs, class lists and queries are not sentences')
        self.assertEqual(send['unnamed'], [('COLD_OUTREACH_PER_HOUR', '5'), ('RETRY_MS', '60 * 1000')])
        self.assertEqual(files['src/chat/window/Header.tsx']['unquoted'], ['Back to chat list'], 'text between tags counts; text with a placeholder does not')
        self.assertEqual(files['src/orders/pay.py']['unnamed'], [('MAX_TOTAL', '5000')])
        article = files['src/help/article.ts']
        self.assertEqual((article['content'], article['sentences'], article['unquoted']), (True, 0, []), 'an article counts as a file only')

    def test_groups_by_folder_and_keeps_an_uncited_folder_as_one_line(self):
        groups = c.folders(self.measured())
        self.assertEqual(sorted(groups), ['src/chat', 'src/chat/window', 'src/help', 'src/orders'])
        self.assertEqual(groups['src/chat/window'], {'files': 2, 'lines': 4, 'cited': 0, 'sentences': 2, 'unquoted': 2, 'limits': 0, 'unnamed': 0})
        self.assertEqual((groups['src/chat']['files'], groups['src/chat']['cited']), (1, 1))
        # nothing cited anywhere: one line per top folder, and never above the folder that was asked for
        self.page('notes/chats.md', 'chats', sources=['README.md'])
        self.assertEqual(sorted(c.folders(self.measured())), ['src'])
        self.assertEqual(sorted(c.folders(self.measured('src/chat'), ['src/chat'])), ['src/chat'])

    def test_report_lists_what_to_read(self):
        status, out, err = self.run_cli()
        self.assertEqual((status, err), (0, ''))
        self.assertIn('coverage: 5 code files, ', out)
        self.assertIn('pages cite 1 of them', out)
        self.assertIn('6 sentences a person can see, 4 on no page; 4 named numbers, 3 on no page', out)
        self.assertIn('1 files that are mostly text (articles, templates) count as files only', out)
        self.assertLess(out.index('src/chat/window'), out.index('src/help'), 'the folder with the most to read comes first')
        self.assertNotIn('things under', out)
        status, out, _ = self.run_cli('--path', 'src/chat/')
        self.assertIn('coverage: 3 code files', out)
        self.assertIn('5 things under src/chat that no page mentions:', out)
        self.assertIn('  src/chat/send.ts says: You cannot remove yourself', out)
        self.assertIn('  src/chat/send.ts sets: RETRY_MS = 60 * 1000', out)
        self.assertIn('2 of 3 files there are cited by no page', out)
        self.assertEqual(self.run_cli('--path', 'nowhere')[1].strip(), 'coverage: no code files found under nowhere')

    def test_a_vault_with_errors_is_reported_and_still_measured(self):
        self.page('notes/bad.md', 'bad', sources=['src/chat/send.ts'], body='[[missing-page]]')
        status, out, err = self.run_cli()
        self.assertEqual(status, 0)
        self.assertIn('the vault has 1 errors', err)
        self.assertIn('coverage: 5 code files', out)


if __name__ == '__main__':
    unittest.main()
