#!/usr/bin/env python3
"""Inspect two committed vault histories without applying or writing changes."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

sys.dont_write_bytecode = True
import knowledge


def git(repo, *args, allow_failure=False):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1',
               GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='')
    result = subprocess.run(['git', '-C', str(repo), '--no-optional-locks', *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode and not allow_failure:
        raise ValueError('git ' + args[0] + ' failed: ' + result.stderr.decode('utf-8', 'replace').strip())
    return result


def text(data):
    return os.fsdecode(data)


def classify(path, prefix):
    if not path.startswith(prefix + '/'):
        return None
    rel = path[len(prefix) + 1:]
    parts = PurePosixPath(rel).parts
    if knowledge.credential_path(rel) or any(p in {'.obsidian', '.trash'} for p in parts):
        return None
    if rel in ('.knowledge/review.json', '.knowledge/sources.json'):
        return 'reviewed_state'
    if rel in ('.knowledge/graph.json', 'Map.canvas', 'graph.html'):
        return 'generated_view'
    if rel in ('.knowledge/sync-plan.json', '.knowledge/sync-status.md', '.knowledge/sync.lock', 'sync.html'):
        return 'local_status'
    if rel.endswith('.md') and '.knowledge' not in parts:
        return 'canonical_markdown'
    return None


def changes(repo, base, commit, prefix):
    raw = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--name-status', '-z', '-M', base, commit, '--').stdout.split(b'\0')
    rows, i = [], 0
    while i < len(raw) and raw[i]:
        status = text(raw[i]); i += 1
        count = 2 if status[0] in 'RC' else 1
        paths = [text(item) for item in raw[i:i + count]]; i += count
        categories = [classify(path, prefix) for path in paths]
        visible = [(path, category) for path, category in zip(paths, categories) if category]
        if visible:
            rows.append({'status': status, 'paths': [item[0] for item in visible],
                         'categories': [item[1] for item in visible]})
    return rows


def tree(repo, commit, prefix):
    # Read tree metadata only; never treat a Git object as a filesystem path.
    raw = git(repo, '--literal-pathspecs', 'ls-tree', '-r', '-z', commit, '--', prefix).stdout
    result = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        path = text(name)
        category = classify(path, prefix)
        if category:
            result[path] = {'mode': text(mode), 'kind': text(kind), 'oid': text(oid), 'category': category}
    return result


def ids(repo, entries):
    result, skipped = {}, []
    for path, item in entries.items():
        if item['category'] != 'canonical_markdown':
            continue
        if item['kind'] != 'blob' or item['mode'] not in ('100644', '100755'):
            skipped.append({'path': path, 'reason': 'not a regular file blob'})
            continue
        blob = git(repo, 'cat-file', 'blob', item['oid']).stdout
        try:
            content = blob.decode('utf-8')
            front = re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|$)', content, re.S)
            if not front or knowledge.has_conflict_markers(content):
                raise ValueError('missing or conflicted frontmatter')
            matches = re.findall(r'^id:\s*(.*?)\s*$', front.group(1), re.M)
            if len(matches) != 1:
                raise ValueError('missing or duplicate id')
            ident = json.loads(matches[0])
            if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9-]+', ident):
                raise ValueError('invalid id')
            result.setdefault(ident, []).append(path)
        except (UnicodeDecodeError, ValueError):
            skipped.append({'path': path, 'reason': 'cannot parse a stable id'})
    return result, skipped


def inspect(repo, vault, ours, theirs):
    if not repo.is_dir() or not vault.is_dir() or not vault.is_relative_to(repo) or repo == vault:
        raise ValueError('repo and vault must be existing directories; vault must be inside repo')
    config = git(repo, 'config', '--get-regexp', r'^(extensions\.partialclone|remote\..*\.promisor)$', allow_failure=True)
    if config.returncode not in (0, 1):
        raise ValueError('cannot inspect Git repository configuration')
    if config.returncode == 0:
        raise ValueError('partial or promisor repository requires full local history')
    top = Path(text(git(repo, 'rev-parse', '--show-toplevel').stdout).strip()).resolve()
    if repo != top:
        raise ValueError('repo must be the worktree root')
    if git(repo, 'rev-parse', '--is-shallow-repository').stdout.strip() == b'true':
        raise ValueError('shallow history cannot establish a reliable merge base')
    # --end-of-options prevents refs from becoming options. Verify explicit commit objects.
    commits = []
    for ref in (ours, theirs):
        if not ref:
            raise ValueError('refs must be nonempty')
        resolved = git(repo, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
        if b'ambiguous' in resolved.stderr.lower():
            raise ValueError('ambiguous ref: ' + ref)
        commits.append(text(resolved.stdout).strip())
    result = git(repo, 'merge-base', '--all', *commits, allow_failure=True)
    bases = text(result.stdout).splitlines()
    if result.returncode or not bases:
        raise ValueError('no common merge base (unrelated histories or invalid history)')
    if len(bases) != 1:
        raise ValueError('multiple merge bases; inspect history manually')
    base, prefix = bases[0], vault.relative_to(repo).as_posix()
    sides = {side: changes(repo, base, commit, prefix) for side, commit in zip(('ours', 'theirs'), commits)}
    trees = {side: tree(repo, commit, prefix) for side, commit in zip(('base', 'ours', 'theirs'), (base, *commits))}
    touched = {side: {path for row in rows for path, category in zip(row['paths'], row['categories']) if category == 'canonical_markdown'} for side, rows in sides.items()}
    our_ids, our_skipped = ids(repo, trees['ours'])
    their_ids, their_skipped = ids(repo, trees['theirs'])
    duplicates = [{'id': ident, 'ours': sorted(our_ids[ident]), 'theirs': sorted(their_ids[ident])}
                  for ident in sorted(our_ids.keys() & their_ids.keys())
                  if any(a != b for a in our_ids[ident] for b in their_ids[ident])]
    state = {}
    for rel in ('.knowledge/review.json', '.knowledge/sources.json'):
        path = prefix + '/' + rel
        values = {side: trees[side].get(path) for side in ('base', 'ours', 'theirs')}
        state[rel] = {'base': values['base'], 'ours': values['ours'], 'theirs': values['theirs'],
                      'different': values['ours'] != values['theirs']}
    unmerged_raw = git(repo, 'ls-files', '-u', '-z').stdout
    unmerged = sorted({text(entry.split(b'\t', 1)[1]) for entry in unmerged_raw.split(b'\0') if entry and b'\t' in entry})
    report = {'base': base, 'ours': commits[0], 'theirs': commits[1], 'changes': sides,
              'shared_canonical_paths': sorted(touched['ours'] & touched['theirs']),
              'duplicate_ids': duplicates, 'reviewed_state': state,
              'unmerged_index_paths': unmerged,
              'skipped_id_paths': {'ours': our_skipped, 'theirs': their_skipped}}
    report['needs_review'] = bool(report['shared_canonical_paths'] or duplicates or unmerged or our_skipped or their_skipped or any(x['different'] for x in state.values()))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect_parser = sub.add_parser('inspect')
    inspect_parser.add_argument('--repo', required=True, type=Path)
    inspect_parser.add_argument('--vault', required=True, type=Path)
    inspect_parser.add_argument('--ours', required=True)
    inspect_parser.add_argument('--theirs', required=True)
    inspect_parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    report = inspect(args.repo.resolve(), args.vault.resolve(), args.ours, args.theirs)
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print('Needs review:' if report['needs_review'] else 'No overlapping candidates detected:')
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
