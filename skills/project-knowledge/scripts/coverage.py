#!/usr/bin/env python3
"""List what the code has that no spec page mentions yet, using only the standard library.

It reads the application's code files and the spec pages and compares three things a spec is supposed to hold:
the files pages cite, the sentences a person can see (messages, labels, empty states) and the numeric limits.
What it prints is a list of places to read, not a score: a sentence that is not on a page may be a button that
only opens something, which the spec leaves out on purpose.
"""
import argparse
import os
import posixpath
import re
import sys
from pathlib import Path

import knowledge

CODE = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte', '.py', '.rb', '.go', '.rs', '.java', '.kt', '.kts',
        '.swift', '.cs', '.php', '.dart', '.ex', '.exs', '.scala', '.sql', '.c', '.cc', '.cpp', '.h', '.m', '.mm'}
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', 'out', 'vendor', 'target', '.next', '.nuxt', '.expo', 'coverage', '__pycache__',
             '.venv', 'venv', 'Pods', '.gradle', 'bin', 'obj', '.turbo', '.cache', 'generated', '__generated__',
             # A migration is the history of the schema, not what the product does today.
             'migrations', 'Migrations', 'migration'}
# A file with this many sentences is text someone wrote for readers (an article, a template, legal terms): the spec
# lists such things, it does not quote them, so they count as files and lines only.
CONTENT_SENTENCES = 40
# Tests, fixtures and stories say what the code does in someone else's words; they are not what a person sees.
TEST_DIR = re.compile(r'(^|/)(tests?|__tests__|__mocks__|__snapshots__|fixtures?|testdata|e2e|stories|specs?|mocks?|seeds?)(/|$)', re.I)
TEST_FILE = re.compile(r'(\.(test|spec|stories|e2e|mock|fixture)\.|_test\.|(^|/)test_[^/]*$|\.d\.ts$|\.min\.|\.generated\.|\.g\.dart$)', re.I)
FILE_LIMIT = 1_000_000
QUOTED = re.compile(r'''(["'`])((?:\\.|(?!\1)[^\\\n])*)\1''')
JSX_TEXT = re.compile(r'>\s*([A-Z][^<>{}\n]{10,200}?)\s*<')
LOG_LINE = re.compile(r'\b(console|logger|log|logging|Sentry|debug)\s*\.\s*\w+\s*\(|^\s*(import|from|describe|it|test|#include|using|package)\b|^\s*(//|#|\*|/\*)')
NOT_PROSE = re.compile(r'[{}<>;=\\]|\$\(|^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH)\b|https?://|\w+\.\w+\(|\w/\w+/\w')
# A named number: MAX_ATTACHMENTS = 10, TTL_MS: number = 60 * 60 * 1000
LIMIT = re.compile(r'\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\s*(?::[^=\n]{1,40})?=\s*([-+]?\d[\d_.]*(?:\s*[*/+-]\s*\d[\d_.]*)*)\s*[;,]?\s*(?:(?://|#).*)?$', re.M)
PUNCTUATION = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', ' ': ' '})


def plain(text):
    """Text as it is compared: case, curly quotes, runs of spaces and Markdown's escaped pipe do not count."""
    return re.sub(r'\s+', ' ', text.translate(PUNCTUATION).replace('\\|', '|')).casefold().strip()


def is_sentence(text):
    """Does this string read like something shown to a person, rather than a key, a class list or a query?"""
    text = text.strip()
    if not 12 <= len(text) <= 200 or not text[0].isupper() or len(text.split()) < 3 or NOT_PROSE.search(text):
        return False
    letters = sum(1 for c in text if c.isalpha() or c == ' ')
    return letters / len(text) >= 0.8


def sentences_in(text):
    found = []
    for line in text.split('\n'):
        if LOG_LINE.search(line):
            continue
        for _, inner in QUOTED.findall(line):
            inner = re.sub(r"\\(['\"`])", r'\1', inner)
            if is_sentence(inner):
                found.append(inner.strip())
        found += [m.strip() for m in JSX_TEXT.findall(line) if is_sentence(m)]
    return list(dict.fromkeys(found))


def code_files(repo, vault):
    """Repository-relative paths of the application's own code: tracked or untracked but not ignored, no tests."""
    listed = knowledge.run_git(repo, ['ls-files', '-z', '--cached', '--others', '--exclude-standard'])
    if listed.returncode == 0:
        names = [os.fsdecode(n) for n in listed.stdout.split(b'\0') if n]
    else:
        names = []
        for folder, dirs, files in os.walk(repo):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.'))
            names += [Path(os.path.relpath(Path(folder) / f, repo)).as_posix() for f in sorted(files)]
    inside = Path(os.path.relpath(vault, repo)).as_posix() + '/'
    return sorted(n for n in names
                  if posixpath.splitext(n)[1].lower() in CODE and not n.startswith(inside)
                  and not any(part in SKIP_DIRS for part in n.split('/')[:-1])
                  and not TEST_DIR.search(posixpath.dirname(n)) and not TEST_FILE.search(n))


def measure(repo, vault, notes, prefixes=()):
    """Per code file: lines, whether a page cites it, and the sentences and limits no page mentions."""
    spec = [n for n in notes if n['meta']['type'] in {'area', 'note'}]
    pages = plain('\n'.join(f"{n['meta']['title']}\n{n['meta'].get('summary', '')}\n{n['body']}" for n in spec))
    words = set(re.findall(r'[A-Z][A-Z0-9_]+', '\n'.join(n['body'] for n in spec)))
    cited = {posixpath.normpath(s) for n in spec for s in n['meta']['sources']}
    files = {}
    for name in code_files(repo, vault):
        if prefixes and not any(name == p or name.startswith(p.rstrip('/') + '/') for p in prefixes):
            continue
        path = repo / name
        try:
            if path.is_symlink() or path.stat().st_size > FILE_LIMIT:
                continue
            text = path.read_bytes().decode('utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        sentences = sentences_in(text)
        content = len(sentences) >= CONTENT_SENTENCES
        if content:
            sentences = []
        limits = list(dict.fromkeys(LIMIT.findall(text)))
        files[name] = {
            'lines': text.count('\n') + 1, 'cited': name in cited, 'content': content, 'sentences': len(sentences), 'limits': len(limits),
            'unquoted': [s for s in sentences if plain(s).rstrip('.!?:…') not in pages],
            'unnamed': [(n, v.strip()) for n, v in limits if n not in words]}
    return files


def folders(files, prefixes=()):
    """Group files into the places to read: a folder no page cites anything in is one line, however deep it goes.

    With prefixes (the folders the caller asked about) a line never names a folder above the one asked for."""
    cited_under = {}
    for name, info in files.items():
        if info['cited']:
            parts = name.split('/')[:-1]
            for i in range(len(parts) + 1):
                cited_under['/'.join(parts[:i])] = True
    groups = {}
    for name, info in files.items():
        parts = name.split('/')[:-1]
        folder = '/'.join(parts)
        floor = max((len(p.split('/')) for p in prefixes if name.startswith(p.rstrip('/') + '/')), default=1)
        # Climb to the highest folder that still has no cited file under it.
        for i in range(min(floor, len(parts)) or 1, len(parts) + 1):
            if not cited_under.get('/'.join(parts[:i])):
                folder = '/'.join(parts[:i])
                break
        g = groups.setdefault(folder or '.', {'files': 0, 'lines': 0, 'cited': 0, 'sentences': 0, 'unquoted': 0, 'limits': 0, 'unnamed': 0})
        g['files'] += 1
        g['lines'] += info['lines']
        g['cited'] += info['cited']
        g['sentences'] += info['sentences']
        g['unquoted'] += len(info['unquoted'])
        g['limits'] += info['limits']
        g['unnamed'] += len(info['unnamed'])
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--vault', type=Path, help='default: the single vault under knowledge/ in the repository')
    parser.add_argument('--path', action='append', default=[], metavar='FOLDER',
                        help='only this folder or file of the repository, and list each sentence and limit no page mentions; repeatable')
    parser.add_argument('--all', action='store_true', help='print every line instead of the first 40 folders or 60 items')
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error('repo must be an existing directory')
    try:
        vault = args.vault.resolve() if args.vault else knowledge.find_vault(repo)
    except ValueError as exc:
        parser.error(str(exc))
    if not vault.is_dir():
        parser.error('repo and vault must be existing directories')
    notes, _, errors, _, _ = knowledge.load_vault(repo, vault, freshness=False, absent=[])
    if errors:
        print(f'coverage: the vault has {len(errors)} errors; pages with errors are not counted (run check)', file=sys.stderr)
    prefixes = [posixpath.normpath(p.replace(os.sep, '/')) for p in args.path]
    files = measure(repo, vault, notes, prefixes)
    if not files:
        print('coverage: no code files found' + (' under ' + ', '.join(prefixes) if prefixes else ''))
        return 0
    total = lambda key: sum(len(f[key]) if isinstance(f[key], list) else f[key] for f in files.values())
    print(f"coverage: {len(files)} code files, {total('lines')} lines; pages cite {total('cited')} of them")
    print(f"coverage: {total('sentences')} sentences a person can see, {total('unquoted')} on no page; "
          f"{total('limits')} named numbers, {total('unnamed')} on no page")
    texts = sum(1 for f in files.values() if f['content'])
    print('coverage: this is a list of places to read, not a score; tests, fixtures, migrations and generated code are left out'
          + (f'; {texts} files that are mostly text (articles, templates) count as files only' if texts else ''))
    groups = sorted(folders(files, prefixes).items(), key=lambda kv: (-(kv[1]['unquoted'] + kv[1]['unnamed']), -kv[1]['lines'], kv[0]))
    shown = groups if args.all else groups[:40]
    width = max(len(name) for name, _ in shown)
    print(f"\n{'folder'.ljust(width)}  files   lines  cited  sentences not on a page  numbers not on a page")
    for name, g in shown:
        print(f"{name.ljust(width)}  {g['files']:5}  {g['lines']:6}  {g['cited']:5}  {g['unquoted']:9} of {g['sentences']:<9}  {g['unnamed']:7} of {g['limits']}")
    if len(groups) > len(shown):
        print(f'... and {len(groups) - len(shown)} more folders (--all prints them)')
    if prefixes:
        items = [(name, 'says', s) for name, f in files.items() for s in f['unquoted']]
        items += [(name, 'sets', f'{n} = {v}') for name, f in files.items() for n, v in f['unnamed']]
        print(f'\n{len(items)} things under {", ".join(prefixes)} that no page mentions:')
        for name, verb, what in (items if args.all else items[:60]):
            print(f'  {name} {verb}: {what}')
        if not args.all and len(items) > 60:
            print(f'  ... and {len(items) - 60} more (--all prints them)')
        uncited = sorted((f['lines'], name) for name, f in files.items() if not f['cited'])
        print(f'\n{len(uncited)} of {len(files)} files there are cited by no page; the largest:')
        for lines, name in reversed(uncited[-(len(uncited) if args.all else 15):]):
            print(f'  {name} ({lines} lines)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
