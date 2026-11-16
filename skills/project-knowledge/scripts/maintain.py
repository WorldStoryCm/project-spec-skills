#!/usr/bin/env python3
"""Plan and explicitly finish integrated project-knowledge reviews."""
import argparse
import contextlib
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

import knowledge

PARTIAL_EXIT = 3  # a partial finish; 2 is argparse's usage error and 1 is any other failure


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(repo, *args, binary=False):
    p = subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise ValueError('git ' + ' '.join(args) + ': ' + p.stderr.decode(errors='replace').strip())
    return p.stdout if binary else p.stdout.decode('utf-8', 'surrogateescape').strip()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.sync-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def safe_bytes(text):
    # Paths that are not valid UTF-8 arrive as lone surrogates; show them as \udcXX escapes.
    return text.encode('utf-8', 'backslashreplace')


def jsonbytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + '\n').encode()


def relevant(path, vault_rel):
    p = Path(path)
    parts = p.parts
    bundle_metadata = vault_rel.startswith('knowledge/') and path in {'knowledge/README.md', 'knowledge/.gitignore'}
    return bool(parts) and not bundle_metadata and not knowledge.credential_path(path) and not (path == vault_rel or path.startswith(vault_rel + '/')) and not (path == 'knowledge/tooling/project-knowledge' or path.startswith('knowledge/tooling/project-knowledge/')) and not any(knowledge.fold(x) in {'.git', 'node_modules', '.next', 'dist', 'build', 'coverage', '__pycache__'} for x in parts)


def housekeeping(path, vault_rel):
    """Paths a sync never queues because they are the vault, the portable skill copy or their wrapper files."""
    if vault_rel.startswith('knowledge/') and path in {'knowledge/README.md', 'knowledge/.gitignore'}:
        return True
    return any(path == base or path.startswith(base + '/') for base in (vault_rel, 'knowledge/tooling/project-knowledge'))


def retarget_hint(repo, vault, target):
    """If HEAD moved past target only through excluded paths, say how to retarget; otherwise None."""
    head = git(repo, 'rev-parse', 'HEAD^{commit}')
    if head == target or subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', target, head]).returncode:
        return None
    try:
        vault_rel = vault.relative_to(repo).as_posix()
    except ValueError:
        return None
    for line in git(repo, 'rev-list', '--reverse', '--parents', target + '..' + head).splitlines():
        commit, *parents = line.split()
        if parents and any(not housekeeping(p, vault_rel) for row in changes(repo, parents[0], commit) for p in row['paths']):
            return None
    return (f'plan target {target} is not HEAD {head}, but every commit in between touches only excluded paths (the vault, the portable skill copy, '
            f'their wrapper files). First set review_target in the run page to the new HEAD (review_target: {head}; review_base stays), '
            'then re-run "scan --write-status" (the plan records the run page\'s bytes, so the page must be edited before the scan), '
            'regenerate the receipt with "receipt", fill in the dispositions and run finish again. Do not commit the vault in between: that would move HEAD again.')


def changes(repo, left, right):
    raw = git(repo, 'diff', '--name-status', '-z', '-M', left, right, '--', binary=True).split(b'\0')
    rows = []
    i = 0
    while i < len(raw) and raw[i]:
        status = os.fsdecode(raw[i]); i += 1
        count = 2 if status[0] in 'RC' else 1
        paths = [os.fsdecode(x) for x in raw[i:i + count]]; i += count
        rows.append({'status': status, 'paths': paths})
    return rows


def dirty(repo):
    raw = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all', binary=True).split(b'\0')
    paths = []
    i = 0
    while i < len(raw) and raw[i]:
        item = os.fsdecode(raw[i]); i += 1
        paths.append(item[3:])
        if 'R' in item[:2] or 'C' in item[:2]:
            paths.append(os.fsdecode(raw[i])); i += 1
    return sorted(set(paths))


def normalized(path):
    return Path(path).as_posix()


class Evidence:
    """Resolve each evidence path once so matching is dictionary/set lookup, not repeated stat calls."""

    def __init__(self, repo):
        self.repo = repo
        self._keys = {}

    def keys(self, path):
        # Casefold is intentionally conservative even on case-sensitive volumes; it
        # also preserves impact when a formerly cited path has been deleted.
        got = self._keys.get(path)
        if got is None:
            inode = None
            try:
                info = knowledge.safe_path(self.repo, path).stat()
                inode = (info.st_dev, info.st_ino)
            except (OSError, ValueError):
                pass
            got = self._keys[path] = (normalized(path).casefold(), inode)
        return got

    def group(self, paths):
        names, inodes = set(), set()
        for path in paths:
            name, inode = self.keys(path)
            names.add(name)
            if inode is not None:
                inodes.add(inode)
        return names, inodes

    def matches(self, group, path):
        name, inode = self.keys(path)
        return name in group[0] or (inode is not None and inode in group[1])


def same_evidence(repo, left, right):
    evidence = Evidence(repo)
    return evidence.matches(evidence.group([right]), left)


def validate_selected_evidence(repo, vault, selected, target):
    """Compare selected working-tree evidence directly with target tree blobs."""
    loaded, _, errors, _, _ = knowledge.load_vault(repo, vault, freshness=False)
    if errors:
        raise ValueError('structural errors while checking evidence: ' + '; '.join(errors))
    by_id = {note['meta']['id']: note for note in loaded}
    for ident in selected:
        note = by_id.get(ident)
        if not note:
            raise ValueError('selected note missing: ' + ident)
        for source in note['meta']['sources']:
            evidence = knowledge.safe_path(repo, source)
            if knowledge.credential_path(source) or knowledge.credential_path(evidence.resolve().relative_to(repo).as_posix()):
                raise ValueError('credential evidence is forbidden: ' + ident)
            if evidence.resolve() != repo / normalized(source):
                raise ValueError('affected note cites aliased evidence; use its canonical path: ' + ident)
            try:
                mode = evidence.lstat().st_mode
            except FileNotFoundError:
                if knowledge.tolerates_missing_source(note['meta'], by_id):
                    continue
                raise ValueError('affected note cites missing evidence: ' + ident)
            if not stat.S_ISREG(mode):
                raise ValueError('affected note evidence must be a regular file: ' + ident)
            # Literal pathspecs prevent special filename syntax from widening lookup.
            raw = git(repo, '--literal-pathspecs', 'ls-tree', '-z', target, '--', source, binary=True)
            entries = [entry for entry in raw.split(b'\0') if entry]
            if len(entries) != 1:
                raise ValueError('affected note cites evidence not tracked in target: ' + ident + ': ' + source)
            header, sep, name = entries[0].partition(b'\t')
            fields = header.split()
            if not sep or name != os.fsencode(source) or len(fields) != 3 or fields[0] not in (b'100644', b'100755') or fields[1] != b'blob':
                raise ValueError('affected note evidence is not a regular tracked target file: ' + ident + ': ' + source)
            blob = git(repo, 'cat-file', 'blob', fields[2].decode('ascii'), binary=True)
            if hashlib.sha256(evidence.read_bytes()).digest() != hashlib.sha256(blob).digest():
                raise ValueError('affected note cites dirty evidence or checkout bytes differ from target blob (e.g. CRLF or smudge): ' + ident + ': ' + source)


def scan(repo, vault, target):
    if Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise ValueError('repo must be the worktree root')
    if not vault.is_relative_to(repo) or vault == repo:
        raise ValueError('vault must be inside this worktree')
    vr = vault.relative_to(repo).as_posix()
    cursorpath = vault / '.knowledge/review.json'
    cursor = json.loads(cursorpath.read_text())
    if cursor.get('schema') != 1 or not isinstance(cursor.get('ref'), str) or not isinstance(cursor.get('reviewed_through'), str):
        raise ValueError('invalid review cursor')
    head = git(repo, 'rev-parse', 'HEAD^{commit}')
    branch_proc = subprocess.run(['git', '-C', str(repo), 'symbolic-ref', '-q', 'HEAD'], capture_output=True, text=True)
    branch = branch_proc.stdout.strip() or '(detached)'
    base = git(repo, 'rev-parse', cursor['reviewed_through'] + '^{commit}')
    tip = git(repo, 'rev-parse', (target or 'HEAD') + '^{commit}')
    blockers = []
    if git(repo, 'rev-parse', '--is-shallow-repository') == 'true':
        blockers.append('shallow history cannot establish complete coverage')
    if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', base, tip]).returncode:
        blockers.append('review cursor is not an ancestor of target')
    if branch != cursor['ref']:
        blockers.append('checkout is not the cursor branch')
    if git(repo, 'diff', '--name-only', '--diff-filter=U', '-z', binary=True):
        blockers.append('worktree has unresolved merge conflicts')
    if tip != head:
        blockers.append('target is not checked out at HEAD; remote evidence cannot be accepted')
    # One call lists the whole range with parents; each line is "commit parent...".
    listing = git(repo, 'rev-list', '--reverse', '--parents', base + '..' + tip).splitlines() if not any('ancestor' in b for b in blockers) else []
    commits = [line.split()[0] for line in listing]
    rows = []
    for line in listing:
        commit, *parents = line.split()
        if parents:
            rows.extend({'commit': commit, **row} for row in changes(repo, parents[0], commit))
    paths = sorted({p for row in rows for p in row['paths'] if relevant(p, vr)})
    rows = [{**row, 'paths': [p for p in row['paths'] if relevant(p, vr)]} for row in rows if any(relevant(p, vr) for p in row['paths'])]
    dirty_paths = [p for p in dirty(repo) if relevant(p, vr)]
    notes, edges, errors, warnings, baseline = knowledge.load_vault(repo, vault)
    evidence = Evidence(repo)
    changed = evidence.group(paths)
    affected = {n['meta']['id']: n for n in notes if any(evidence.matches(changed, source) for source in list(n['meta']['sources']) + list(baseline.get(n['meta']['id'], {})))}
    sources = sorted({p for n in notes for p in n['meta']['sources']} | set(paths) | set(dirty_paths))
    source_hashes = {}
    skipped_sources = []
    for source in sources:
        try:
            path = knowledge.safe_path(repo, source)
            resolved = path.resolve().relative_to(repo).as_posix()
            if knowledge.credential_path(source) or knowledge.credential_path(resolved):
                skipped_sources.append(source)
                continue
            source_hashes[source] = digest(path)
        except (ValueError, OSError):
            skipped_sources.append(source)
    dirty_group = evidence.group(dirty_paths)
    dirty_affected = sorted(n['meta']['id'] for n in notes if any(evidence.matches(dirty_group, source) for source in n['meta']['sources']))
    note_hashes = {n['meta']['id']: {'path': n['path'], 'sha256': digest(vault / n['path']), 'sources': n['meta']['sources'], 'areas': n['meta']['areas']} for n in notes}
    mapped = evidence.group({normalized(p) for n in affected.values() for p in list(n['meta']['sources']) + list(baseline.get(n['meta']['id'], {}))})
    return {'schema': 1, 'scanned_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'repo': str(repo), 'vault': str(vault), 'git_dir': git(repo, 'rev-parse', '--absolute-git-dir'), 'branch': branch, 'head': head, 'target': tip, 'base': base, 'cursor_sha256': digest(cursorpath), 'baseline_sha256': digest(vault / '.knowledge/sources.json'), 'commits': commits, 'changes': rows, 'paths': paths, 'dirty': dirty_paths, 'dirty_affected_notes': dirty_affected, 'skipped_sources': skipped_sources, 'affected_notes': sorted(affected), 'affected_areas': sorted({a for n in affected.values() for a in n['meta']['areas']}), 'unmapped': [path for path in paths if not evidence.matches(mapped, path)], 'source_hashes': source_hashes, 'notes': note_hashes, 'errors': errors, 'warnings': warnings, 'blockers': blockers, 'state': 'blocked' if blockers or errors else ('pending' if paths or dirty_paths or warnings else 'ready')}


@contextlib.contextmanager
def lock(vault):
    path = knowledge.output_path(vault, '.knowledge/sync.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('knowledge sync lock already exists')
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def status(vault, plan):
    data = jsonbytes(plan)
    state = {'ready': 'ready', 'pending': 'needs review', 'blocked': 'blocked'}[plan['state']]
    if plan['state'] == 'pending' and not plan['paths'] and not plan['warnings']:
        state = 'local changes pending'
    lines = ['State: ' + state, 'Scanned: ' + plan['scanned_at'],
             'Branch: ' + plan['branch'] + ' at ' + plan['head'],
             'Commit range: ' + plan['base'] + '..' + plan['target'], '',
             f"Integrated changes awaiting review: {len(plan['paths'])} paths; {len(plan['affected_notes'])} affected notes.",
             f"Uncommitted working-tree changes: {len(plan['dirty'])} paths; {len(plan['dirty_affected_notes'])} affected notes.", '',
             'An empty commit queue does not mean the entire project has been researched.', '',
             'Blockers and errors:']
    lines += ['- ' + x for x in plan['blockers'] + plan['errors']] or ['- None']
    lines += ['', 'Source freshness warnings:'] + (['- ' + x for x in plan['warnings']] or ['- None'])
    lines += ['', 'Changes without linked notes:'] + (['- ' + x for x in plan['unmapped']] or ['- None'])
    lines += ['', 'Notes affected by working-tree changes:'] + (['- ' + x for x in plan['dirty_affected_notes']] or ['- None'])
    lines += ['', 'Skipped unsafe sources:'] + (['- ' + x for x in plan['skipped_sources']] or ['- None'])
    lines += ['', 'Changed paths in commits:'] + (['- ' + x for x in plan['paths']] or ['- None'])
    lines += ['', 'Uncommitted changes:'] + (['- ' + x for x in plan['dirty']] or ['- None'])
    lines += ['', 'Affected notes:'] + (['- ' + x for x in plan['affected_notes']] or ['- None'])
    text = '# Knowledge sync status\n\n' + '\n'.join(lines) + '\n'
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Knowledge sync status</title><style>body{font:16px/1.6 system-ui,sans-serif;'
            'max-width:70rem;margin:auto;padding:1.5rem;color:#222}pre{font:inherit;white-space:pre-wrap;'
            'overflow-wrap:anywhere}a{color:#164cb5}</style><h1>Knowledge sync status</h1>'
            '<p>To read the spec, run <code>knowledge.py serve --repo .</code></p><pre>' + html.escape('\n'.join(lines)) + '</pre></html>')
    for name, content in [('.knowledge/sync-plan.json', data), ('.knowledge/sync-status.md', safe_bytes(text)), ('sync.html', safe_bytes(page))]:
        atomic(knowledge.output_path(vault, name), content)


def finish(repo, vault, plan_path, review_path):
    """Return (message, exit code): 0 when the checkpoint advanced or nothing was pending, PARTIAL_EXIT (3, distinct from argparse's usage error 2) for a partial finish."""
    plan_bytes = plan_path.read_bytes()
    plan, review = json.loads(plan_bytes), json.loads(review_path.read_bytes())
    if review.get('plan_sha256') != hashlib.sha256(plan_bytes).hexdigest():
        raise ValueError('review does not match exact plan bytes')
    with lock(vault):
        now = scan(repo, vault, plan['target'])
        if now['head'] != plan['head']:
            hint = retarget_hint(repo, vault, plan['target'])
            if hint:
                raise ValueError(hint)
        for key in ('repo', 'vault', 'git_dir', 'branch', 'head', 'target', 'base', 'cursor_sha256', 'baseline_sha256', 'commits', 'changes', 'paths', 'dirty', 'source_hashes', 'affected_notes', 'affected_areas', 'dirty_affected_notes', 'unmapped', 'skipped_sources'):
            if now[key] != plan[key]:
                raise ValueError('plan changed: ' + key)
        if now['blockers'] or now['errors']:
            raise ValueError('scan has blockers or structural errors: ' + '; '.join(now['blockers'] + now['errors']))
        paths, notes = review.get('paths'), review.get('notes')
        if not isinstance(paths, dict) or set(paths) != set(plan['paths']) or not isinstance(notes, dict) or set(notes) != set(plan['affected_notes']):
            raise ValueError('receipt must cover exactly all integrated paths and affected notes')
        for path, decision in paths.items():
            if not isinstance(decision, dict) or decision.get('status') not in ('reviewed', 'excluded', 'deferred') or not isinstance(decision.get('reason'), str) or not decision['reason'].strip():
                raise ValueError('path needs reviewed/excluded/deferred decision and reason: ' + path)
            if path in plan['dirty'] and decision['status'] != 'deferred':
                raise ValueError('dirty integrated path must be deferred (or cleaned and rescanned): ' + path)
        ev = Evidence(repo)
        excluded = ev.group([path for path, decision in paths.items() if decision['status'] == 'excluded'])
        deferred_paths = {path: decision['reason'].strip() for path, decision in paths.items() if decision['status'] == 'deferred'}
        deferred_group = ev.group(deferred_paths)
        dirty_now = ev.group(now['dirty'])
        baseline_file = vault / '.knowledge/sources.json'
        baseline = json.loads(baseline_file.read_text()) if baseline_file.is_file() else {}
        accepted, deferred_notes = [], {}
        for ident, old in plan['notes'].items():
            current = now['notes'].get(ident)
            if current is None or current['path'] != old['path']:
                raise ValueError('note set or path changed: ' + ident)
            if ident in notes:
                decision = notes[ident]
                if not isinstance(decision, dict) or decision.get('status') not in ('updated', 'unchanged', 'deferred') or decision.get('expected_sha256') != current['sha256']:
                    raise ValueError('note requires updated/unchanged/deferred decision with expected hash: ' + ident)
                if decision['status'] == 'deferred':
                    if not isinstance(decision.get('reason'), str) or not decision['reason'].strip():
                        raise ValueError('deferred note needs a reason: ' + ident)
                    deferred_notes[ident] = decision['reason'].strip()
                    continue
                if decision['status'] == 'unchanged' and current != old:
                    raise ValueError('unchanged note was modified: ' + ident)
                if any(ev.matches(excluded, source) for source in current['sources']):
                    raise ValueError('affected note cites excluded evidence: ' + ident)
                for source in current['sources']:
                    evidence = knowledge.safe_path(repo, source)
                    if evidence.resolve() != repo / normalized(source):
                        raise ValueError('affected note cites aliased evidence; use its canonical path: ' + ident)
                    if ev.matches(dirty_now, source):
                        raise ValueError('affected note cites dirty evidence (mark the note deferred): ' + ident)
                for source in list(current['sources']) + list(baseline.get(ident, {})):
                    if ev.matches(deferred_group, source):
                        raise ValueError('affected note cites a deferred path (mark the note deferred): ' + ident + ': ' + source)
                if any(s not in plan['source_hashes'] or plan['source_hashes'][s] != now['source_hashes'].get(s) for s in current['sources']):
                    raise ValueError('new or changed source requires rescan: ' + ident)
                accepted.append(ident)
            elif current != old:
                raise ValueError('unreviewed note changed: ' + ident)
        if set(now['notes']) != set(plan['notes']):
            raise ValueError('note set changed; rescan required')
        validate_selected_evidence(repo, vault, accepted, plan['target'])
        if not plan['paths']:
            return 'no substantive integrated paths; cursor unchanged', 0
        run_path = review.get('run_path')
        if not isinstance(run_path, str) or not run_path.startswith('runs/') or not run_path.endswith('.md'):
            raise ValueError('receipt requires a runs/*.md run_path')
        run = knowledge.output_path(vault, run_path)
        planned_run = next((n for n in plan['notes'].values() if n['path'] == run_path), None)
        current_run = next((n for n in now['notes'].values() if n['path'] == run_path), None)
        if not run.is_file() or not planned_run or not current_run or review.get('run_sha256') != digest(run) or planned_run['sha256'] != digest(run):
            raise ValueError('run must exist at scan time and match its receipt hash')
        run_notes, _, _, _, _ = knowledge.load_vault(repo, vault, freshness=False)
        run_note = next((n for n in run_notes if n['path'] == run_path), None)
        if not run_note or run_note['meta']['type'] != 'run' or run_note['meta'].get('review_base') != plan['base'] or run_note['meta'].get('review_target') != plan['target']:
            raise ValueError('run note must identify the exact reviewed base and target')
        partial = bool(deferred_paths or deferred_notes)
        with tempfile.TemporaryDirectory(prefix='knowledge-sync-') as temp:
            staged = Path(temp) / 'vault'
            shutil.copytree(vault, staged, symlinks=True)
            if accepted and knowledge.main(['snapshot', '--repo', str(repo), '--vault', str(staged), '--notes', *sorted(accepted)]) != 0:
                raise ValueError('snapshot validation failed')
            if knowledge.main(['check', '--repo', str(repo), '--vault', str(staged)]) != 0 or knowledge.main(['build', '--repo', str(repo), '--vault', str(staged)]) != 0:
                raise ValueError('structural check or build failed')
            # Validate all output destinations before publishing anything.
            outputs = ['.knowledge/sources.json', '.knowledge/graph.json', 'AS-BUILT.md', 'GAPS.md', '.knowledge/review.json']
            destinations = [knowledge.output_path(vault, p) for p in outputs]
            cursor = json.loads((vault / '.knowledge/review.json').read_text())
            checkpoint = cursor['reviewed_through']
            cursor['reviewed_through'] = plan['target']; cursor['run_path'] = run_path
            latest = scan(repo, vault, plan['target'])
            for key in ('head', 'branch', 'cursor_sha256', 'baseline_sha256', 'source_hashes', 'dirty', 'notes'):
                if latest[key] != now[key]:
                    raise ValueError('review changed before publication: ' + key)
            validate_selected_evidence(repo, vault, accepted, plan['target'])
            staged_baseline = json.loads((staged / '.knowledge/sources.json').read_text())
            for ident in accepted:
                expected = {source: now['source_hashes'][source] for source in now['notes'][ident]['sources'] if now['source_hashes'].get(source) is not None}
                if staged_baseline.get(ident) != expected:
                    raise ValueError('staged evidence changed during snapshot: ' + ident)
            backups = {dest: dest.read_bytes() if dest.exists() else None for dest in destinations}
            written = []
            try:
                for name, dest in zip(outputs[:-1], destinations[:-1]):
                    atomic(dest, (staged / name).read_bytes()); written.append(dest)
                if not partial:  # the checkpoint moves only when nothing applicable is deferred
                    atomic(destinations[-1], jsonbytes(cursor)); written.append(destinations[-1])
            except OSError:
                for dest in reversed(written):
                    if backups[dest] is None:
                        dest.unlink(missing_ok=True)
                    else:
                        atomic(dest, backups[dest])
                raise
        if partial:
            lines = [f'partial: accepted {len(accepted)} notes; deferred {len(deferred_paths)} paths, {len(deferred_notes)} notes; checkpoint stays at {checkpoint}']
            lines += [f'deferred path {p}: {r}' for p, r in sorted(deferred_paths.items())]
            lines += [f'deferred note {n}: {r}' for n, r in sorted(deferred_notes.items())]
            return '\n'.join(lines), PARTIAL_EXIT
        return 'review checkpoint advanced to ' + plan['target'], 0


def receipt(repo, vault, plan_path, out, run=None):
    """Write a review receipt with every hash filled in and each status/reason left empty.

    An existing receipt keeps the statuses and reasons already entered for entries that still apply.
    """
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    if plan.get('vault') != str(vault):
        raise ValueError('plan was written for a different vault')
    hint = retarget_hint(repo, vault, plan['target'])
    if hint:
        raise ValueError(hint)
    previous = {}
    if out.exists():
        previous = json.loads(out.read_bytes())
        if not isinstance(previous, dict):
            raise ValueError('existing receipt is not a JSON object')
    old_paths = previous.get('paths') if isinstance(previous.get('paths'), dict) else {}
    old_notes = previous.get('notes') if isinstance(previous.get('notes'), dict) else {}

    def kept(table, key, field):
        entry = table.get(key)
        value = entry.get(field) if isinstance(entry, dict) else None
        return value if isinstance(value, str) else ''

    plan_hash = hashlib.sha256(plan_bytes).hexdigest()
    same_plan = previous.get('plan_sha256') == plan_hash  # path dispositions belong to the plan they reviewed
    def entered(table, key):
        return bool(kept(table, key, 'status'))

    count = {'kept_paths': 0, 'reset_paths': 0, 'kept_notes': 0, 'reset_notes': [], 'dropped_paths': 0, 'dropped_notes': 0}
    for p in plan['paths']:
        if entered(old_paths, p):
            count['kept_paths' if same_plan else 'reset_paths'] += 1
    count['dropped_paths'] = sum(1 for p in old_paths if p not in plan['paths'] and entered(old_paths, p))
    count['dropped_notes'] = sum(1 for n in old_notes if n not in plan['affected_notes'] and entered(old_notes, n))
    result = {'plan_sha256': plan_hash,
              'paths': {p: {'status': kept(old_paths, p, 'status') if same_plan else '', 'reason': kept(old_paths, p, 'reason') if same_plan else ''} for p in plan['paths']},
              'notes': {}}
    for ident in plan['affected_notes']:
        file = knowledge.safe_path(vault, plan['notes'][ident]['path'])
        current = digest(file)
        # A note disposition belongs to the exact bytes that were reviewed.
        keep = kept(old_notes, ident, 'expected_sha256') == current
        result['notes'][ident] = {'status': kept(old_notes, ident, 'status') if keep else '', 'expected_sha256': current}
        if keep and kept(old_notes, ident, 'reason'):
            result['notes'][ident]['reason'] = kept(old_notes, ident, 'reason')
        if entered(old_notes, ident):
            if keep:
                count['kept_notes'] += 1
            else:
                count['reset_notes'].append(ident)
    if run is not None:
        run_path = run.resolve().relative_to(vault).as_posix() if run.is_absolute() else run.as_posix()
    elif plan['paths']:
        loaded, _, _, _, _ = knowledge.load_vault(repo, vault, freshness=False)
        found = [n['path'] for n in loaded if n['meta']['type'] == 'run' and n['path'].startswith('runs/')
                 and n['meta'].get('review_base') == plan['base'] and n['meta'].get('review_target') == plan['target']]
        if len(found) != 1:
            raise ValueError(f'found {len(found)} run notes for this range; pass --run runs/NAME.md')
        run_path = found[0]
    else:
        run_path = None
    if run_path is not None:
        if not run_path.startswith('runs/') or not run_path.endswith('.md'):
            raise ValueError('run must be a runs/*.md path inside the vault')
        file = knowledge.output_path(vault, run_path)
        if not file.is_file():
            raise ValueError('run note does not exist: ' + run_path)
        result['run_path'] = run_path
        result['run_sha256'] = digest(file)
    atomic(out, jsonbytes(result))
    message = f"receipt written: fill status and reason for {len(result['paths'])} paths and status for {len(result['notes'])} notes"
    if any(count[k] for k in ('kept_paths', 'reset_paths', 'kept_notes', 'reset_notes', 'dropped_paths', 'dropped_notes')):
        reset_paths = f" ({'plan changed since the receipt was written'})" if count['reset_paths'] else ''
        reset_notes = f" (note file changed: {', '.join(count['reset_notes'])})" if count['reset_notes'] else ''
        message += (f"\ndispositions kept: {count['kept_paths']} paths, {count['kept_notes']} notes; "
                    f"reset: {count['reset_paths']} paths{reset_paths}, {len(count['reset_notes'])} notes{reset_notes}; "
                    f"dropped (no longer in the plan): {count['dropped_paths']} paths, {count['dropped_notes']} notes")
    return message


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='command', required=True)
    rp = subs.add_parser('receipt')
    rp.add_argument('--repo', required=True, type=Path); rp.add_argument('--vault', required=True, type=Path)
    rp.add_argument('--plan', required=True, type=Path); rp.add_argument('--out', required=True, type=Path)
    rp.add_argument('--run', type=Path)
    for name in ('scan', 'finish'):
        p = subs.add_parser(name); p.add_argument('--repo', required=True, type=Path); p.add_argument('--vault', required=True, type=Path)
        if name == 'scan':
            p.add_argument('--target'); p.add_argument('--write-status', action='store_true'); p.add_argument('--json', action='store_true')
        else:
            p.add_argument('--plan', required=True, type=Path); p.add_argument('--review', required=True, type=Path)
    args = parser.parse_args(); repo = args.repo.resolve(); vault = args.vault.resolve()
    if args.command == 'receipt':
        print(receipt(repo, vault, args.plan, args.out, args.run))
    elif args.command == 'scan':
        report = scan(repo, vault, args.target)
        if args.write_status:
            with lock(vault): status(vault, report)
            if not args.json:
                print('plan_sha256:', digest(vault / '.knowledge/sync-plan.json'))
        print(json.dumps(report, ensure_ascii=True, indent=2) if args.json else f"{report['state']}: {len(report['paths'])} integrated paths, {len(report['affected_notes'])} affected notes, {len(report['blockers']) + len(report['errors'])} blockers/errors")
    else:
        message, code = finish(repo, vault, args.plan, args.review)
        print(message)
        return code
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print('ERROR:', exc, file=sys.stderr); sys.exit(1)
