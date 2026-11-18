#!/usr/bin/env python3
"""Validate and build a project-knowledge vault using only the standard library."""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import posixpath
import re
import sys
import subprocess
import tempfile
import unicodedata
from urllib.parse import unquote, urlsplit
from pathlib import Path, PurePosixPath

TYPES = {'index', 'area', 'note', 'gap', 'plan', 'run'}
SPEC_STATUSES = {'current', 'partial', 'stale', 'superseded'}
NAV_STATUSES = SPEC_STATUSES | {'planned'}
KINDS = ('product-gap', 'verification-gap', 'product-plan', 'conflict', 'knowledge-gap')
RECHECKS = ('not-checked', 'confirmed', 'not-reproduced', 'outdated')
DECISIONS = ('open', 'accepted', 'rejected', 'deferred', 'done', 'duplicate')
DECIDED = ('accepted', 'rejected', 'deferred')
STATE_ORDER = ('needs-recheck', 'needs-decision', 'accepted', 'deferred', 'rejected', 'done', 'duplicate')
GAP_ONLY = ('kind', 'recheck', 'rechecked_by', 'rechecked_on', 'decision', 'decided_by', 'decided_on', 'duplicate_of')
GAP_SECTIONS = ('Current behavior', 'Gap', 'Evidence', 'Recheck', 'Discussion', 'Decision')
LAYERS = {'area': 'spec', 'note': 'spec', 'gap': 'gap', 'plan': 'gap', 'index': 'nav', 'run': 'nav'}
UNCOUNTED = ' (uncommitted change, not counted)'  # suffix of a freshness warning that --ignore-dirty does not count
CONTROL = re.compile('[\x00-\x1f\x7f\x85\u2028\u2029]')
SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
MD_LINK = re.compile(r'\]\(\s*(<[^>]*>|[^\s)]*)')
# The delimiter row of a GFM table: | --- | :-: |, with or without the outer pipes, at least one pipe.
TABLE_RULE = re.compile(r'^ {0,3}\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$|^ {0,3}\|[ \t]*:?-+:?[ \t]*\|?[ \t]*$')
# A numbered business rule: the first cell of a table row, e.g. | BR-PROFILE-01 | ... |
RULE_ROW = re.compile(r'^ {0,3}\|[ \t]*(BR-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{2,4})[ \t]*\|')
MD_REF = re.compile(r'^ {0,3}\[[^\]\n]+\]:\s*(<[^>]*>|\S+)', re.M)
GAP_PAGE_ONLY = ('priority', 'confidence')
ARRAYS = {'areas', 'sources', 'tags', 'aliases', 'task_ids'}
STRINGS = {'id', 'title', 'type', 'status', 'updated', 'summary', 'verification', 'priority', 'confidence', 'gap',
           *GAP_ONLY}
REQUIRED = {'id', 'title', 'type', 'areas', 'sources', 'updated'}
LINK = re.compile(r'(!?)\[\[([^\[\]\n]+)\]\]')  # no brackets inside, so a run of '[[' cannot backtrack
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
HEADING = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$')
CREDENTIAL_NAMES = {'.env', '.aws', '.ssh', '.gnupg', 'credentials', 'secrets', '.npmrc', '.netrc', '.htpasswd',
                    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa', '.git', '.git-credentials', 'credentials.json',
                    '.envrc', '.pgpass', '.pypirc', '_netrc', '.vault-token', '.terraformrc',
                    'application_default_credentials.json'}
CREDENTIAL_SUFFIXES = ('.pem', '.key', '.p12', '.pfx', '.tfstate', '.tfstate.backup', '.jks', '.ppk', '.p8', '.tfvars', '.gpg')
CREDENTIAL_PAIRS = {('.kube', 'config'), ('.docker', 'config.json')}


def safe_path(root, value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value:
        raise ValueError('path must be relative and stay inside its root')
    candidate = root.joinpath(*p.parts)
    if not candidate.resolve().is_relative_to(root):
        raise ValueError('path resolves outside its root')
    return candidate


def output_path(root, value):
    path = safe_path(root, value)
    current = root
    for part in PurePosixPath(value).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'output path contains symlink: {value}')
    return path


def fold(part):
    """Compatibility-fold a path part so look-alike characters (e.g. U+017F) cannot dodge name checks."""
    return unicodedata.normalize('NFKC', part).casefold()


def credential_path(value):
    parts = [fold(p) for p in PurePosixPath(value).parts]
    if any(pair in CREDENTIAL_PAIRS for pair in zip(parts, parts[1:])):
        return True
    return any(p in CREDENTIAL_NAMES or p.startswith('.env.') or p.endswith(CREDENTIAL_SUFFIXES) or
               (p.startswith('service-account') and p.endswith('.json')) or
               (p.startswith('client_secret') and p.endswith('.json')) or p.startswith('secrets.') for p in parts)


def lines_with_code(body, state=None):
    """Yield (line, in_code) following CommonMark fenced code rules.

    A backtick opener cannot have a backtick in its info string, and a closer
    cannot have an info string at all.
    """
    fence = None
    for line in re.split(r'\r\n|\n|\r', body):
        match = FENCE.match(line)
        if fence is None:
            if match and not (match.group(1)[0] == '`' and '`' in match.group(2)):
                fence = (match.group(1)[0], len(match.group(1)))
                yield line, True
            else:
                yield line, False
        else:
            yield line, True
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1] and not match.group(2).strip():
                fence = None
    if state is not None:
        state['fence'] = fence  # still open when the text ended


def prose(body):
    return '\n'.join(re.sub(r'(`+).*?\1', '', line) for line, in_code in lines_with_code(body) if not in_code)


def heading_of(line):
    """Return (level, text) for an ATX heading line, else None."""
    match = HEADING.match(line)
    if not match:
        return None
    return len(match.group(1)), re.sub(r'(?:^|[ \t]+)#+$', '', match.group(2) or '').strip()


def sections(body):
    """Return [(name or None, text)] for each level-1/2 heading outside code, in order."""
    found, current = [], None
    for line, in_code in lines_with_code(body):
        head = None if in_code else heading_of(line)
        if head and head[0] <= 2:
            current = (head[1] if head[0] == 2 else None, [])
            found.append(current)
        elif current is not None:
            current[1].append(line)
    return [(name, '\n'.join(lines)) for name, lines in found]


def atomic_write(path, text):
    """Write text next to its destination and replace it, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = os.umask(0)
    os.umask(mask)
    mode = path.stat().st_mode & 0o777 if path.is_file() else 0o666 & ~mask
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.knowledge-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(text.encode('utf-8'))
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def check_date(key, value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'{key} must be YYYY-MM-DD')
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{key} is not a real date')


def gap_state(meta):
    """Derived, never stored: needs-recheck, needs-decision, or the decision itself."""
    if meta['decision'] != 'open':
        return meta['decision']
    return 'needs-recheck' if meta['recheck'] in {'not-checked', 'outdated'} else 'needs-decision'


def validate_meta(meta):
    """Raise ValueError with an author-facing message for the first frontmatter problem."""
    missing = REQUIRED - meta.keys()
    if missing:
        raise ValueError('missing properties: ' + ', '.join(sorted(missing)))
    for key in STRINGS & meta.keys():
        if not isinstance(meta[key], str):
            raise ValueError(f'{key} must be a string')
    for key in ARRAYS & meta.keys():
        if not isinstance(meta[key], list) or any(not isinstance(x, str) for x in meta[key]):
            raise ValueError(f'{key} must be a string array')
    for key in (STRINGS | ARRAYS) & meta.keys():
        for value in (meta[key] if isinstance(meta[key], list) else [meta[key]]):
            if CONTROL.search(value):
                raise ValueError(f'{key} must not contain control characters (line breaks, tabs, U+0085, U+2028, U+2029)')
    if not re.fullmatch(r'[a-z0-9-]+', meta['id']):
        raise ValueError('invalid id')
    kind = meta['type']
    if not meta['title'].strip() or kind not in TYPES:
        raise ValueError('invalid title or type; type must be one of ' + ', '.join(sorted(TYPES)))
    check_date('updated', meta['updated'])
    if kind in {'note', 'gap', 'plan'} and not meta['areas']:
        raise ValueError(f'{kind} requires an area')
    if kind == 'gap':
        if 'status' in meta:
            raise ValueError('a gap must not have status; gaps use recheck and decision instead')
        validate_gap(meta)
    else:
        for key in GAP_ONLY:
            if key in meta:
                raise ValueError(f'{key} is only valid on gap pages')
        if kind != 'plan':
            for key in GAP_PAGE_ONLY:
                if key in meta:
                    raise ValueError(f'{key} is only valid on gap and plan pages')
        if kind in {'area', 'note'}:
            for key in ('title', 'summary'):
                if re.search(r'\[\[|\[[^\]\n]*\]\([^)\n]*\)', meta.get(key, '')):
                    raise ValueError(f'{key} of a spec page must not contain links; describe the page in plain text')
        if 'status' not in meta:
            raise ValueError('missing properties: status')
        allowed = SPEC_STATUSES if kind in {'area', 'note'} else NAV_STATUSES
        if meta['status'] not in allowed:
            hint = ''
            if meta['status'] in {'unverified', 'conflict'}:
                hint = f"; '{meta['status']}' is no longer a status: record it as a gap under gaps/"
            raise ValueError(f"status must be one of {', '.join(sorted(allowed))}{hint}")
        if kind == 'note' and meta['status'] == 'current' and not meta['sources']:
            raise ValueError('current note requires sources')
    if kind == 'plan':
        if not meta.get('gap', '').strip():
            raise ValueError('plan requires gap: the id of the accepted gap it implements')
    elif 'gap' in meta:
        raise ValueError('gap is only valid on plan pages')


def validate_gap(meta):
    for key, values in (('kind', KINDS), ('recheck', RECHECKS), ('decision', DECISIONS)):
        if key not in meta:
            raise ValueError(f'gap requires {key} (one of {", ".join(values)})')
        if meta[key] not in values:
            raise ValueError(f'{key} must be one of {", ".join(values)}')
    if meta['recheck'] == 'not-checked':
        for key in ('rechecked_by', 'rechecked_on'):
            if key in meta:
                raise ValueError(f"{key} must be absent while recheck is 'not-checked'")
    else:
        for key in ('rechecked_by', 'rechecked_on'):
            if key not in meta:
                raise ValueError(f"{key} is required when recheck is '{meta['recheck']}'")
        if not meta['rechecked_by'].strip():
            raise ValueError('rechecked_by must name a person, or be "agent"')
        check_date('rechecked_on', meta['rechecked_on'])
    if meta['decision'] == 'open':
        for key in ('decided_by', 'decided_on'):
            if key in meta:
                raise ValueError(f"{key} must be absent while decision is 'open'")
    elif meta['decision'] in DECIDED:
        for key in ('decided_by', 'decided_on'):
            if key not in meta:
                raise ValueError(f"{key} is required when decision is '{meta['decision']}'")
    if 'decided_by' in meta and (not meta['decided_by'].strip() or meta['decided_by'].strip().lower() == 'agent'):
        raise ValueError("decided_by must be a person's name: an agent may not decide, only record what a person decided")
    if 'decided_on' in meta:
        check_date('decided_on', meta['decided_on'])
    if meta['decision'] == 'duplicate':
        if not meta.get('duplicate_of', '').strip():
            raise ValueError("duplicate_of is required when decision is 'duplicate': give the id of the other gap")
    elif 'duplicate_of' in meta:
        raise ValueError("duplicate_of is only valid when decision is 'duplicate'")


def has_conflict_markers(content):
    # Git emits labeled openers; keep candidates of different widths independent.
    active = {}
    for line in content.splitlines():
        opener = re.fullmatch(r'(<+)[ \t]+\S.*', line)
        if opener:
            active.setdefault(len(opener.group(1)), set()).add(1)
        for width, states in active.items():
            if 1 in states and re.fullmatch(r'\|{' + str(width) + r'}(?:[ \t].*)?', line):
                states.add(2)
            if (1 in states or 2 in states) and line == '=' * width:
                states.add(3)
            if 3 in states and re.fullmatch(r'>{' + str(width) + r'}(?:[ \t].*)?', line):
                return True
    return False


def tolerates_missing_source(meta, ids):
    """Missing sources only warn on stale/superseded pages, closed gaps and plans of done gaps."""
    if meta.get('status') in {'stale', 'superseded'}:
        return True
    if meta['type'] == 'gap':
        return meta['decision'] in {'done', 'rejected', 'duplicate'}
    if meta['type'] == 'plan':
        return ids.get(meta['gap'], {}).get('meta', {}).get('decision') == 'done'
    return False


def markdown_target(rel, raw):
    """Vault-relative path a Markdown link points at, or None for URLs, anchors and absolute paths."""
    target = unquote(re.split(r'[?#]', raw[1:-1] if raw.startswith('<') else raw, maxsplit=1)[0])
    if not target or target.startswith('/') or SCHEME.match(target):
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))


def attachment_exists(vault, target, cache):
    """Embedded non-Markdown files (images, PDFs) resolve by path or bare name anywhere in the vault."""
    if not cache:
        cache['names'], cache['paths'] = set(), set()
        for file in vault.rglob('*'):
            parts = file.relative_to(vault).parts
            if file.is_file() and not any(part in {'.obsidian', '.trash', '.knowledge'} for part in parts):
                cache['names'].add(parts[-1].casefold())
                cache['paths'].add('/'.join(parts).casefold())
    wanted = target.casefold()
    return wanted in cache['paths'] or ('/' not in wanted and wanted in cache['names'])


def line_ending_variant(data, old):
    """True when data matches the baseline digest after converting all line endings to LF or CRLF."""
    lf = data.replace(b'\r\n', b'\n')
    return old in {hashlib.sha256(lf).hexdigest(), hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest()}


def head_blob(repo, source):
    """Bytes of the source as committed at HEAD, or None when HEAD has no such file (untracked, new or no commits)."""
    result = subprocess.run(['git', '-C', str(repo), 'cat-file', 'blob', f'HEAD:./{posixpath.normpath(source)}'], capture_output=True)
    return None if result.returncode else result.stdout


def uncommitted_paths(repo):
    """Repo-relative paths Git reports as modified, staged or untracked (one status call), or None outside a work tree."""
    probe = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--is-inside-work-tree', '--show-prefix'], capture_output=True)
    lines = probe.stdout.decode(errors='replace').split('\n')
    if probe.returncode or lines[0] != 'true':
        return None
    prefix = lines[1] if len(lines) > 1 else ''
    status = subprocess.run(['git', '-C', str(repo), 'status', '--porcelain=v1', '-z', '--untracked-files=all'], capture_output=True)
    if status.returncode:
        return None
    raw, found, i = status.stdout.split(b'\0'), set(), 0
    while i < len(raw) and raw[i]:
        item = os.fsdecode(raw[i])
        i += 1
        names = [item[3:]]
        if 'R' in item[:2] or 'C' in item[:2]:
            names.append(os.fsdecode(raw[i]))
            i += 1
        found.update(name[len(prefix):] for name in names if name.startswith(prefix))
    return found


def error_page(message):
    """The vault-relative page an error message is about, or None for vault-wide errors."""
    head = message.split(': ', 1)[0]
    return head if head.endswith('.md') else None


def load_vault(repo, vault, freshness=True, dirty=None, report=None, absent=None):
    """dirty: repo-relative paths with uncommitted changes. Their freshness warning is marked, not counted, only when
    the accepted fingerprint equals the file's HEAD blob (up to LF/CRLF), so the sole drift is uncommitted.

    absent, when given, collects cited files that are not there instead of reporting them: for a build that sees
    only part of the repository, such as a Docker build context. Their pages are not marked as changed.

    report, when given, receives 'failed': {page path: parsed id or None} for pages that failed validation.
    """
    errors, warnings, notes, failed, failed_kind, cascade = [], [], [], {}, {}, []
    baseline_file = vault / '.knowledge/sources.json'
    baseline = {}
    if baseline_file.exists():
        try:
            safe_path(vault, '.knowledge/sources.json')
            baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
            if not isinstance(baseline, dict) or any(not isinstance(v, dict) for v in baseline.values()):
                raise ValueError('expected object of note source maps')
        except (OSError, ValueError) as exc:
            errors.append(f'Invalid source snapshot: {exc}')
            baseline = {}
    for file in sorted(vault.rglob('*.md')):
        relative = file.relative_to(vault)
        if any(part in {'.obsidian', '.trash', '.knowledge'} for part in relative.parts):
            continue
        rel = relative.as_posix()
        meta = None
        try:
            safe_path(vault, rel)
            content = file.read_text(encoding='utf-8').removeprefix('\ufeff')
            if has_conflict_markers(content):
                raise ValueError('unresolved Git conflict markers')
            match = re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|$)', content, re.S)
            if not match:
                raise ValueError('missing frontmatter')
            meta = {}
            for line in match.group(1).splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                key, sep, value = line.partition(':')
                if not sep or not re.fullmatch(r'[a-z_]+', key) or key in meta:
                    raise ValueError('invalid or duplicate property')
                meta[key] = json.loads(value.strip())
            validate_meta(meta)
            notes.append({'meta': meta, 'path': rel, 'body': content[match.end():]})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f'{rel}: {exc}')
            # The page still exists as a link target; only its own errors are real.
            ident = meta.get('id') if isinstance(meta, dict) else None
            failed[rel] = ident if isinstance(ident, str) and re.fullmatch(r'[a-z0-9-]+', ident) else None
            kind = meta.get('type') if isinstance(meta, dict) else None
            failed_kind[rel] = kind if kind in TYPES else None
    failed_ids = {i for i in failed.values() if i}
    failed_id_kinds = {}
    for rel, ident in failed.items():
        if ident:
            failed_id_kinds.setdefault(ident, set()).add(failed_kind[rel])
    failed_stems = {rel[:-3]: failed_kind[rel] for rel in failed}
    failed_names = {}
    for stem, kind in failed_stems.items():
        failed_names.setdefault(PurePosixPath(stem).name, []).append(kind)
    ids, paths, basenames = {}, {}, {}
    for note in notes:
        meta, rel = note['meta'], note['path']
        if meta['id'] in ids:
            errors.append(f"{rel}: duplicate id {meta['id']}")
        ids[meta['id']] = note
        stem = rel[:-3]
        paths[stem] = note
        basenames.setdefault(PurePosixPath(stem).name, []).append(note)
    area_ids = {n['meta']['id'] for n in notes if n['meta']['type'] == 'area'}
    edges, attachments, rule_pages = set(), {}, {}
    for note in notes:
        meta, rel = note['meta'], note['path']
        note['stale'] = False
        if meta['type'] == 'gap':
            note['state'] = gap_state(meta)
        if meta['type'] == 'gap' and meta.get('duplicate_of'):
            other = ids.get(meta['duplicate_of'])
            if other is None and meta['duplicate_of'] in failed_ids and failed_id_kinds[meta['duplicate_of']] & {None, 'gap'}:
                cascade.append(f"{rel}: duplicate_of {meta['duplicate_of']} names a page that failed validation")
            elif other is None or other['meta']['type'] != 'gap':
                errors.append(f"{rel}: duplicate_of {meta['duplicate_of']} is not the id of an existing gap")
            elif other is note:
                errors.append(f'{rel}: duplicate_of must name a different gap')
        if meta['type'] == 'plan':
            other = ids.get(meta['gap'])
            if other is None and meta['gap'] in failed_ids and failed_id_kinds[meta['gap']] & {None, 'gap'}:
                cascade.append(f"{rel}: gap {meta['gap']} names a page that failed validation")
            elif other is None or other['meta']['type'] != 'gap':
                errors.append(f"{rel}: gap {meta['gap']} is not the id of an existing gap")
            else:
                edges.add((meta['id'], other['meta']['id']))
            if other is not None and other['meta']['type'] == 'gap' and other['meta']['decision'] not in {'accepted', 'done'}:
                errors.append(f"{rel}: gap {meta['gap']} has decision '{other['meta']['decision']}'; a plan needs an accepted or done gap")
        if meta['type'] == 'gap':
            found = [name for name, _ in sections(note['body']) if name is not None]
            for name in GAP_SECTIONS:
                if found.count(name) != 1:
                    errors.append(f"{rel}: gap needs exactly one '## {name}' section (found {found.count(name)})")
            texts = {name: text for name, text in sections(note['body']) if name in GAP_SECTIONS}
            if meta['decision'] != 'open' and found.count('Decision') == 1 and not texts['Decision'].strip():
                errors.append(f"{rel}: the Decision section must say who decided and why once decision is '{meta['decision']}'")
            if meta['recheck'] != 'not-checked' and found.count('Recheck') == 1 and not texts['Recheck'].strip():
                errors.append(f"{rel}: the Recheck section must say what was checked once recheck is '{meta['recheck']}'")
        for area in meta['areas']:
            if area not in ids and area in failed_ids and failed_id_kinds[area] & {None, 'area'}:
                # Only the "missing" error is hidden; a failed page known to be another type still reports it.
                cascade.append(f'{rel}: area {area} names a page that failed validation')
                continue
            if area not in area_ids:
                errors.append(f'{rel}: unknown area {area}')
            elif area != meta['id']:
                edges.add((area, meta['id']))
        text = prose(note['body'])
        run_links = 0
        for embed, link in LINK.findall(text):
            # Inside Markdown tables Obsidian requires the alias separator to be written as \|.
            target = re.split(r'\\?\|', link, maxsplit=1)[0].split('#', 1)[0].split('^', 1)[0].strip()
            if not target:
                continue
            if target.endswith('.md'):
                target = target[:-3]
            choices = basenames.get(target, []) if '/' not in target else ([paths[target]] if target in paths else [])
            broken_kinds = failed_names.get(target, []) if '/' not in target else ([failed_stems[target]] if target in failed_stems else [])
            broken = len(broken_kinds)
            if broken == 1 and not choices:
                # The one candidate exists but failed validation; its own errors are the root cause of "missing".
                if meta['type'] in {'area', 'note'} and broken_kinds[0] in {'gap', 'plan'}:
                    errors.append(f"{rel}: spec pages must not link to the gap layer ({'embed ' if embed else ''}{target}); link from the gap to this page instead")
                else:
                    cascade.append(f'{rel}: link {target} names a page that failed validation')
                    if meta['type'] == 'run':
                        run_links += 1
                continue
            if embed and not choices and PurePosixPath(target).suffix:
                # Not a note: Obsidian embeds images and PDFs by file name.
                if not attachment_exists(vault, target, attachments):
                    errors.append(f'{rel}: missing embed {target}')
                continue
            if len(choices) + broken != 1:
                errors.append(f"{rel}: {'ambiguous' if len(choices) + broken > 1 else 'missing'} {'embed' if embed else 'wikilink'} {target}")
            elif meta['type'] in {'area', 'note'} and choices[0]['meta']['type'] in {'gap', 'plan'}:
                errors.append(f"{rel}: spec pages must not link to the gap layer ({'embed ' if embed else ''}{target}); link from the gap to this page instead")
            elif meta['type'] == 'run':
                run_links += 1
            elif meta['type'] == 'area' and choices[0]['meta']['type'] == 'note' and re.search(r'[#^]', re.split(r'\\?\|', link, maxsplit=1)[0]):
                errors.append(f"{rel}: an area page links whole notes, not a part of one ({link.split('|')[0].replace(chr(92), '')}); "
                              "if that part needs its own link, make it its own note and list it here")
            else:
                edges.add((meta['id'], choices[0]['meta']['id']))
        if meta['type'] == 'area':
            # An area page is a map of its notes. A table on it is behavior written in the wrong place.
            tables = sum(1 for line in text.split('\n') if TABLE_RULE.match(line))
            if tables:
                errors.append(f"{rel}: an area page is a map and holds no table ({tables} found); a table describes behavior: "
                              "write a note for each thing it describes and list the notes on the area page")
        if meta['type'] == 'note':
            # People quote a rule by its number in tickets, tests and chats, so a number means one rule for good.
            seen = set()
            for line in text.split('\n'):
                rule = RULE_ROW.match(line)
                if not rule:
                    continue
                ident = rule.group(1)
                first = rule_pages.setdefault(ident, rel)
                if first != rel or ident in seen:
                    errors.append(f"{rel}: rule {ident} is numbered twice ({'on this page' if first == rel else 'also on ' + first}); "
                                  "a rule keeps its number and a number is never used again, so give the newer rule the next free one")
                seen.add(ident)
        if meta['type'] in {'area', 'note'}:
            gap_files = {n['path'].casefold() for n in notes if n['meta']['type'] in {'gap', 'plan'}} | {'gaps.md'}
            gap_files |= {f.casefold() for f, kind in failed_kind.items() if kind in {'gap', 'plan'}}
            unknown_files = {f.casefold() for f, kind in failed_kind.items() if kind is None}
            for raw in MD_LINK.findall(text) + MD_REF.findall(text):
                resolved = markdown_target(rel, raw)
                if resolved is not None and resolved.casefold() in gap_files:
                    errors.append(f"{rel}: spec pages must not link to the gap layer ({raw.strip('<>')}); link from the gap to this page instead")
                elif resolved is not None and resolved.casefold() in unknown_files:
                    cascade.append(f'{rel}: link {raw.strip("<>")} names a page that failed validation')
        if meta['type'] == 'run':
            # A run touches many pages; as links they would turn it into a hub that glues every cluster together.
            page_files = {n['path'].casefold() for n in notes} | {f.casefold() for f in failed}
            run_links += sum(1 for raw in MD_LINK.findall(text) + MD_REF.findall(text)
                             if (markdown_target(rel, raw) or '').casefold() in page_files)
            if run_links:
                errors.append(f"{rel}: run pages are history, not part of the map, and must not link to vault pages ({run_links} link{'s' if run_links != 1 else ''}); name a page by its path in code formatting, e.g. `notes/example`")
        closed = tolerates_missing_source(meta, ids)
        note['changed'] = False
        for source in meta['sources']:
            try:
                if credential_path(source):
                    raise ValueError('credential source is forbidden')
                path = safe_path(repo, source)
                if credential_path(path.resolve().relative_to(repo).as_posix()):
                    raise ValueError('credential source is forbidden')
                if not path.is_file():
                    if absent is not None and not path.exists():
                        absent.append(source)
                        continue
                    if closed:
                        warnings.append(f'{rel}: missing source {source}')
                        note['stale'] = True
                        continue
                    raise ValueError('source is missing or not a file')
                if freshness:
                    old = baseline.get(meta['id'], {}).get(source)
                    data = path.read_bytes()
                    if old != hashlib.sha256(data).hexdigest():
                        mark = ''
                        if old and dirty is not None and posixpath.normpath(source) in dirty:
                            # Forgive only pure uncommitted drift: the accepted bytes are what HEAD holds (up to line endings).
                            blob = head_blob(repo, source)
                            if blob is not None and (hashlib.sha256(blob).hexdigest() == old or line_ending_variant(blob, old)):
                                mark = UNCOUNTED
                        if old and line_ending_variant(data, old):
                            warnings.append(f'{rel}: line endings differ in source {source}{mark}')
                        else:
                            note['changed'] = note['changed'] or bool(old)
                            warnings.append(f"{rel}: {'changed' if old else 'unbaselined'} source {source}{mark}")
                        note['stale'] = True
            except (OSError, ValueError) as exc:
                errors.append(f'{rel}: {source}: {exc}')
    if report is not None:
        report['failed'] = failed
        report['cascade'] = cascade
    return notes, sorted(edges), errors, warnings, baseline


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def recheck_marker(note):
    """Automatic marker: a recorded recheck exists but a cited source's bytes changed since its fingerprint."""
    return note['meta']['recheck'] in {'confirmed', 'not-reproduced'} and bool(note.get('changed'))


FILE_LIMIT = 300_000    # characters of one cited file sent to the viewer
FILES_LIMIT = 4_000_000  # characters of all cited files together


def cited_files(repo, vault, notes):
    """Text of the repository files the pages cite, so the viewer can show them instead of sending the reader to a raw file.

    Keys are repository-relative paths. Only files inside the repository and outside the vault are taken, never
    credential paths, binaries or symlinks that leave the repository. Returns (files, skipped paths).
    """
    wanted = set()
    for note in notes:
        for source in note['meta']['sources']:
            wanted.add(posixpath.normpath(source))
        text = prose(note['body'])
        for raw in MD_LINK.findall(text) + MD_REF.findall(text):
            target = markdown_target(note['path'], raw)
            if target is not None:
                wanted.add(Path(os.path.relpath(os.path.normpath(vault / target), repo)).as_posix())
    files, skipped, total = {}, [], 0
    for rel in sorted(wanted):
        if rel.startswith('../') or rel in ('..', '.') or credential_path(rel):
            continue
        file = repo / rel
        try:
            resolved = file.resolve()
            if not file.is_file() or not resolved.is_relative_to(repo) or resolved.is_relative_to(vault):
                continue
            data = file.read_bytes()
            if b'\0' in data:
                continue
            text = data.decode('utf-8')
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        truncated = len(text) > FILE_LIMIT
        if truncated:
            text = text[:FILE_LIMIT].rsplit('\n', 1)[0]
        if total + len(text) > FILES_LIMIT:
            skipped.append(rel)
            continue
        total += len(text)
        files[rel] = {'text': text, 'truncated': truncated}
    return files, skipped


def node_of(note):
    m = note['meta']
    gap = m['type'] == 'gap'
    return {k: m[k] for k in ('id', 'title', 'type', 'areas', 'sources', 'updated')} | {
        'status': '' if gap else m['status'],
        'tags': m.get('tags', []), 'path': note['path'], 'body': note['body'],
        'summary': m.get('summary', ''), 'stale': note['stale'],
        'kind': m.get('kind', ''), 'recheck': m.get('recheck', ''), 'recheckedBy': m.get('rechecked_by', ''),
        'recheckedOn': m.get('rechecked_on', ''), 'decision': m.get('decision', ''), 'decidedBy': m.get('decided_by', ''),
        'decidedOn': m.get('decided_on', ''), 'priority': m.get('priority', ''), 'confidence': m.get('confidence', ''),
        'duplicateOf': m.get('duplicate_of', ''), 'recheckOutdated': gap and (m['recheck'] == 'outdated' or recheck_marker(note)), 'state': note.get('state', ''), 'gap': m.get('gap', ''),
        'layer': LAYERS[m['type']]}


def graph_of(notes, edges, warnings):
    nodes = [node_of(note) for note in notes]
    title = next((n['title'] for n in nodes if n['path'] == '00-index.md'), 'Project knowledge')
    return {'title': title, 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'nodes': nodes,
            'edges': [{'source': a, 'target': b} for a, b in edges], 'warnings': warnings}


def viewer_html(payload):
    template = (Path(__file__).resolve().parent.parent / 'assets/viewer.html').read_text(encoding='utf-8')
    if template.count('__KNOWLEDGE_DATA__') != 1:
        raise ValueError('viewer template must contain exactly one placeholder')
    serialized = json.dumps(payload, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return template.replace('__KNOWLEDGE_DATA__', serialized)


def find_vault(repo):
    """The vault of a repository when there is exactly one in the usual place."""
    found = sorted(p.parent for p in repo.glob('knowledge/*/00-index.md'))
    if (repo / 'knowledge/00-index.md').is_file():
        found.append(repo / 'knowledge')
    if len(found) != 1:
        raise ValueError(('no vault found under knowledge/' if not found else
                          'several vaults found (' + ', '.join(p.relative_to(repo).as_posix() for p in found) + ')') + '; pass --vault')
    return found[0]


HISTORY_COMMITS = 30  # commits shown under Recent changes
HISTORY_PAGES = 80    # pages listed for one commit
_history_cache = {}


def page_pathspec(repo, vault):
    """Git pathspec for the vault's own pages (no generated files), and the prefix to strip from the paths Git prints."""
    rel = Path(os.path.relpath(vault, repo)).as_posix()
    if rel == '..' or rel.startswith('../'):
        return None, None
    prefix = '' if rel == '.' else rel + '/'
    return [f':(glob){prefix}**/*.md', f':(exclude,glob){prefix}AS-BUILT.md', f':(exclude,glob){prefix}GAPS.md',
            f':(exclude,glob){prefix}.knowledge/**'], prefix


def front_value(line):
    """The string a `key: "value"` frontmatter line holds, as the vault writes it (a JSON string)."""
    raw = line.split(':', 1)[1].strip()
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw
    return value if isinstance(value, str) else ''


def shallow_commits(repo):
    """Commits whose parents a shallow clone left out. Empty in a full clone and outside Git."""
    found = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--git-path', 'shallow'], capture_output=True)
    if found.returncode:
        return set()
    try:
        return set((repo / os.fsdecode(found.stdout).strip()).read_text(encoding='ascii').split())
    except (OSError, UnicodeDecodeError):
        return set()


def vault_history(repo, vault):
    """Recent commits that touched vault pages, newest first: sha, date, subject and what happened to each page.

    A page entry carries `was` and `now` when its summary (or, failing that, its title) changed in that commit.
    Empty outside a Git work tree. Cached per HEAD, because every page load asks for it.
    """
    spec, prefix = page_pathspec(repo, vault)
    if spec is None:
        return []
    head = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True)
    if head.returncode:
        return []
    key = (str(repo), str(vault), head.stdout.strip())
    if key in _history_cache:
        return _history_cache[key]
    # Git prints paths from the top of the work tree, which may be above the repository folder given here.
    top = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--show-prefix'], capture_output=True).stdout.decode(errors='replace').strip()
    prefix = top + prefix
    # A marker nobody could have written into a commit message or a page beforehand separates the commits.
    marker = '\x01' + os.urandom(12).hex() + '\x01'
    try:
        log = subprocess.run(['git', '-C', str(repo), '-c', 'core.quotepath=off', 'log', f'-n{HISTORY_COMMITS}', '--date=short', '--no-color',
                              '--no-renames', '-p', '-U0', f'--format={marker}%H%x02%ad%x02%s', '--', *spec],
                             capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return []
    if log.returncode:
        return []
    commits, boundary = [], shallow_commits(repo)
    for chunk in log.stdout.decode('utf-8', errors='replace').split(marker)[1:]:
        header, _, body = chunk.partition('\n')
        sha, date, subject = (header.split('\x02', 2) + ['', ''])[:3]
        if sha in boundary:  # its parents were not fetched, so Git would show every page as added
            continue
        subject = CONTROL.sub('', subject)
        pages, page = [], None
        for line in body.split('\n'):
            if line.startswith('diff --git '):
                name = line.rsplit(' b/', 1)[-1]
                page = {'path': name[len(prefix):], 'status': 'changed', 'fields': {}} if name.startswith(prefix) else None
                if page:
                    pages.append(page)
            elif page is None:
                continue
            elif line.startswith('new file mode'):
                page['status'] = 'added'
            elif line.startswith('deleted file mode'):
                page['status'] = 'removed'
            elif line[:1] in '+-' and line[1:].startswith(('summary:', 'title:')):
                field = line[1:].split(':', 1)[0]
                page['fields'].setdefault(field, {})['now' if line[0] == '+' else 'was'] = front_value(line[1:])
        for page in pages:
            fields = page.pop('fields')
            change = next((fields[f] for f in ('summary', 'title') if fields.get(f, {}).get('was') != fields.get(f, {}).get('now')), {})
            if page['status'] == 'changed' and change.get('was') and change.get('now'):
                page['was'], page['now'] = change['was'], change['now']
        if pages:
            commits.append({'sha': sha, 'date': date, 'subject': subject, 'pages': pages[:HISTORY_PAGES], 'more': max(0, len(pages) - HISTORY_PAGES)})
    _history_cache.clear()
    _history_cache[key] = commits
    return commits


def vault_pending(repo, vault):
    """Vault pages with uncommitted changes: [{path, status}], empty outside Git."""
    spec, prefix = page_pathspec(repo, vault)
    if spec is None:
        return []
    status = subprocess.run(['git', '-C', str(repo), '-c', 'core.quotepath=off', 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames', '--', *spec],
                            capture_output=True)
    if status.returncode:
        return []
    top = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--show-prefix'], capture_output=True).stdout.decode(errors='replace').strip()
    pending = []
    for item in status.stdout.split(b'\0'):
        text = os.fsdecode(item)
        name = text[3:]
        name = name[len(top):] if name.startswith(top) else name
        if len(text) > 3 and name.startswith(prefix):
            code = text[:2]
            pending.append({'path': name[len(prefix):],
                            'status': 'added' if '?' in code or 'A' in code else 'removed' if 'D' in code else 'changed'})
    return sorted(pending, key=lambda p: p['path'])


def page_payload(repo, vault, notes, edges, warnings, sources=True):
    files = cited_files(repo, vault, notes)[0] if sources else {}
    return graph_of(notes, edges, warnings) | {
        'vaultPath': Path(os.path.relpath(vault, repo)).as_posix(), 'files': files,
        'history': vault_history(repo, vault), 'pending': vault_pending(repo, vault)}


def live_page(repo, vault):
    """The viewer for the vault as it is on disk right now, or a page listing what stops it from loading."""
    try:
        notes, edges, errors, warnings, _ = load_vault(repo, vault)
    except (OSError, ValueError) as exc:
        notes, errors = [], [str(exc)]
    if errors:
        items = ''.join(f'<li>{html.escape(message)}</li>' for message in errors)
        return ('<!doctype html><meta charset="utf-8"><title>Spec cannot be shown</title>'
                '<body style="font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:48px auto;padding:0 20px">'
                f'<h1>The spec has {len(errors)} error{"s" if len(errors) != 1 else ""}</h1>'
                '<p>Fix the pages below (the <code>check</code> command prints the same list), then reload.</p>'
                f'<ul>{items}</ul></body>')
    return viewer_html(page_payload(repo, vault, notes, edges, warnings) | {'live': True})


def source_base(value, commit):
    """The address `--source-url` names, with `{commit}` filled in. Raises ValueError with the reason when it cannot be used."""
    if CONTROL.search(value) or ' ' in value or not re.match(r'https?://[^/]', value, re.I):
        raise ValueError('--source-url must be an http(s) address, e.g. https://github.com/OWNER/REPO/blob/{commit}')
    if '{commit}' in value and not commit:
        raise ValueError('--source-url names {commit}, but --repo is not a Git work tree with a commit')
    return value.replace('{commit}', commit).rstrip('/')


def built_page(repo, vault, notes, edges, warnings, with_sources=False, source_url=''):
    """The viewer as one file to put on a server: the vault as it is now, with nothing read later.

    The text of cited repository files is left out unless asked for, because the file may be shown to people
    who cannot read the repository. Returns (html, payload).
    """
    head = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True)
    commit = '' if head.returncode else head.stdout.decode('ascii', errors='replace').strip()
    payload = page_payload(repo, vault, notes, edges, warnings, with_sources) | {
        'built': True, 'commit': commit, 'sourceUrl': source_base(source_url, commit) if source_url else ''}
    return viewer_html(payload), payload


def make_server(repo, vault, port):
    """A read-only viewer on this machine only. Each page load reads the vault and the cited files again."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # The page carries source code, so answer only when addressed as this machine (no DNS rebinding).
            host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]')
            if host not in ('127.0.0.1', 'localhost', '::1'):
                return self.send_error(403)
            if urlsplit(self.path).path not in ('/', '/index.html'):
                return self.send_error(404)
            body = live_page(repo, vault).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'snapshot', 'serve', 'build'])
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--vault', type=Path, help='default: the single vault under knowledge/ in the repository')
    parser.add_argument('--strict', action='store_true', help='fail check when freshness warnings exist')
    parser.add_argument('--port', type=int, default=8757, help='serve: port on 127.0.0.1 (another free port is used if it is taken)')
    parser.add_argument('--open', action='store_true', help='serve: open the page in the default browser')
    parser.add_argument('--out', type=Path, help='build: the HTML file to write, outside the vault')
    parser.add_argument('--with-sources', action='store_true', help='build: include the text of the repository files the pages cite')
    parser.add_argument('--source-url', default='', help='build: where a cited file can be read, e.g. https://github.com/OWNER/REPO/blob/{commit}')
    parser.add_argument('--allow-missing-sources', action='store_true',
                        help='build: do not stop when a cited file is not there, for a build that sees only part of the repository')
    parser.add_argument('--ignore-dirty', action='store_true',
                        help='check: do not count freshness warnings for sources with uncommitted changes (needs a Git work tree)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true')
    group.add_argument('--notes', nargs='+')
    args = parser.parse_args(argv)
    if args.strict and args.command != 'check':
        parser.error('--strict is only for check')
    if args.ignore_dirty and args.command != 'check':
        parser.error('--ignore-dirty is only for check')
    if args.open and args.command != 'serve':
        parser.error('--open is only for serve')
    if args.command == 'build' and not args.out:
        parser.error('build requires --out FILE')
    if args.command != 'build' and (args.out or args.with_sources or args.source_url or args.allow_missing_sources):
        parser.error('--out, --with-sources, --source-url and --allow-missing-sources are only for build')
    if args.command == 'snapshot' and not (args.all or args.notes):
        parser.error('snapshot requires --all or --notes')
    if args.command != 'snapshot' and (args.all or args.notes):
        parser.error('--all and --notes are only for snapshot')
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error('repo must be an existing directory')
    vault = args.vault.resolve() if args.vault else find_vault(repo)
    if not vault.is_dir():
        parser.error('repo and vault must be existing directories')
    if args.command == 'serve':
        try:
            server = make_server(repo, vault, args.port)
        except OSError:  # the usual port is taken
            server = make_server(repo, vault, 0)
        url = f'http://127.0.0.1:{server.server_address[1]}/'
        print(f'serve: {url} shows {vault} as it is on disk; reload the page after a change, Ctrl+C to stop', flush=True)
        if args.open:
            import webbrowser
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    dirty = None
    if args.ignore_dirty:
        dirty = uncommitted_paths(repo)
        if dirty is None:
            parser.error('--ignore-dirty needs --repo to be a Git work tree')
    report = {}
    absent = [] if args.allow_missing_sources else None
    notes, edges, errors, warnings, baseline = load_vault(repo, vault, args.command != 'snapshot', dirty, report, absent)
    ignored = []
    if args.command == 'snapshot' and args.notes:
        # Only the selected pages must be valid; errors elsewhere are counted, not blocking.
        wanted = set(args.notes)
        by_id = {n['meta']['id']: n['path'] for n in notes}
        by_id.update({ident: page for page, ident in report['failed'].items() if ident})
        selected = {by_id[i] for i in wanted if i in by_id}
        blocking = []
        for message in errors:
            page = error_page(message)
            if page is None or page in selected or any(f'duplicate id {i}' in message for i in wanted):
                blocking.append(message)
            else:
                ignored.append(message)
        # A selected page that leans on a page which failed validation cannot be accepted yet.
        blocking += [m for m in report['cascade'] if error_page(m) in selected]
        errors = blocking
        missing = wanted - by_id.keys()
        if missing:
            errors.append('Unknown note IDs: ' + ', '.join(sorted(missing)))
    for message in errors:
        print('ERROR:', message, file=sys.stderr)
    for message in warnings:
        print('WARNING:', message, file=sys.stderr)
    counted = [w for w in warnings if not w.endswith(UNCOUNTED)]
    if errors:
        pages = len({error_page(m) for m in errors if error_page(m)})
        print(f'{args.command}: failed, {len(errors)} errors on {pages} pages', file=sys.stderr)
    if errors or (args.strict and counted):
        return 1
    if ignored:
        print(f'{args.command}: {len(ignored)} errors on {len({error_page(m) for m in ignored if error_page(m)})} other pages do not block this snapshot (run check to see them)', file=sys.stderr)
    if args.command == 'build':
        out = Path(os.path.abspath(args.out))
        if out.is_dir() or out.resolve().is_relative_to(vault):
            parser.error('--out must be a file outside the vault: nothing is generated into the vault')
        try:
            page, payload = built_page(repo, vault, notes, edges, warnings, args.with_sources, args.source_url)
        except ValueError as exc:
            parser.error(str(exc))
        atomic_write(out, page)
        files = len(payload['files'])
        print(f'build: wrote {out} ({len(page.encode("utf-8")) // 1024} kB), {len(notes)} notes, {len(warnings)} warnings'
              + (f', commit {payload["commit"][:7]}' if payload['commit'] else ''))
        print('build: ' + (f'the text of {files} cited source files is inside the file; show it only to people who may read the repository'
                           if args.with_sources else 'cited source files are named but their text is not included (--with-sources adds it)'))
        if absent:
            names = sorted(set(absent))
            print(f'build: {len(names)} cited files are not in this folder, so nobody compared them with the pages: ' + ', '.join(names[:8]) + (' ...' if len(names) > 8 else ''))
        if shallow_commits(repo):
            print('build: this is a shallow clone, so the Changes page starts at the first commit that was fetched in full; fetch the whole history to show more')
        return 0
    if args.command == 'snapshot':
        for note in notes:
            meta = note['meta']
            if args.all or meta['id'] in args.notes:
                hashes = {}
                for source in meta['sources']:
                    path = safe_path(repo, source)
                    if path.is_file():
                        hashes[source] = hashlib.sha256(path.read_bytes()).hexdigest()
                baseline[meta['id']] = hashes
        dest = output_path(vault, '.knowledge/sources.json')
        write_json(dest, dict(sorted(baseline.items())))
    uncounted = len(warnings) - len(counted)
    print(f'{args.command}: {len(notes)} notes, {len(edges)} links, {len(warnings)} warnings' + (f' ({uncounted} uncommitted, not counted)' if uncounted else ''))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
