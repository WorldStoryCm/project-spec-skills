#!/usr/bin/env python3
"""Validate and build a project-knowledge vault using only the standard library."""
import argparse
import datetime as dt
import hashlib
import json
import os
import posixpath
import re
import sys
import subprocess
import tempfile
import unicodedata
from urllib.parse import unquote
from pathlib import Path, PurePosixPath

TYPES = {'index', 'area', 'note', 'gap', 'plan', 'run'}
SPEC_STATUSES = {'current', 'partial', 'stale', 'superseded'}
NAV_STATUSES = SPEC_STATUSES | {'planned'}
KINDS = ('product-gap', 'verification-gap', 'product-plan', 'conflict', 'knowledge-gap')
RECHECKS = ('not-checked', 'confirmed', 'not-reproduced', 'outdated')
RECHECK_WORDS = {'confirmed': 'confirmed (still holds)', 'not-reproduced': 'not reproduced (no longer holds)'}  # shown in GAPS.md only
DECISIONS = ('open', 'accepted', 'rejected', 'deferred', 'done', 'duplicate')
DECIDED = ('accepted', 'rejected', 'deferred')
STATE_ORDER = ('needs-recheck', 'needs-decision', 'accepted', 'deferred', 'rejected', 'done', 'duplicate')
GAP_ONLY = ('kind', 'recheck', 'rechecked_by', 'rechecked_on', 'decision', 'decided_by', 'decided_on', 'duplicate_of')
GAP_SECTIONS = ('Current behavior', 'Gap', 'Evidence', 'Recheck', 'Discussion', 'Decision')
LAYERS = {'area': 'spec', 'note': 'spec', 'gap': 'gap', 'plan': 'gap', 'index': 'nav', 'run': 'nav'}
RESERVED = {'AS-BUILT.md', 'GAPS.md'}  # generated at the vault root; never notes
UNCOUNTED = ' (uncommitted change, not counted)'  # suffix of a freshness warning that --ignore-dirty does not count
GENERATED_NAMES = ('AS-BUILT.md', 'GAPS.md', 'graph.html', 'Map.canvas')  # matched case-insensitively
CONTROL = re.compile('[\x00-\x1f\x7f\x85\u2028\u2029]')
SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
MD_LINK = re.compile(r'\]\(\s*(<[^>]*>|[^\s)]*)')
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


def is_generated(file):
    """A root file with a generated name is ours only if it starts with the generated banner."""
    try:
        with open(file, encoding='utf-8') as handle:
            return handle.readline().rstrip('\r\n') == GENERATED
    except (OSError, UnicodeDecodeError):
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


def load_vault(repo, vault, freshness=True, dirty=None, report=None):
    """dirty: repo-relative paths with uncommitted changes whose freshness warnings are marked, not counted.

    report, when given, receives 'failed': {page path: parsed id or None} for pages that failed validation.
    """
    errors, warnings, notes, failed = [], [], [], {}
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
        if rel in RESERVED and is_generated(file):
            continue
        if len(relative.parts) == 1 and rel.casefold() in {n.casefold() for n in GENERATED_NAMES}:
            errors.append(f'{rel}: this name is reserved for a generated file (AS-BUILT.md, GAPS.md); build would overwrite it, so rename the page')
            continue
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
    if report is not None:
        report['failed'] = failed
    failed_ids = {i for i in failed.values() if i}
    failed_stems = {rel[:-3] for rel in failed}
    failed_names = {}
    for stem in failed_stems:
        failed_names[PurePosixPath(stem).name] = failed_names.get(PurePosixPath(stem).name, 0) + 1
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
    edges, attachments = set(), {}
    for note in notes:
        meta, rel = note['meta'], note['path']
        note['stale'] = False
        if meta['type'] == 'gap':
            note['state'] = gap_state(meta)
        if meta['type'] == 'gap' and meta.get('duplicate_of'):
            other = ids.get(meta['duplicate_of'])
            if other is None and meta['duplicate_of'] in failed_ids:
                pass
            elif other is None or other['meta']['type'] != 'gap':
                errors.append(f"{rel}: duplicate_of {meta['duplicate_of']} is not the id of an existing gap")
            elif other is note:
                errors.append(f'{rel}: duplicate_of must name a different gap')
        if meta['type'] == 'plan':
            other = ids.get(meta['gap'])
            if other is None and meta['gap'] in failed_ids:
                pass
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
            if area in failed_ids and area not in area_ids:
                continue
            if area not in area_ids:
                errors.append(f'{rel}: unknown area {area}')
            elif area != meta['id']:
                edges.add((area, meta['id']))
        text = prose(note['body'])
        for embed, link in LINK.findall(text):
            # Inside Markdown tables Obsidian requires the alias separator to be written as \|.
            target = re.split(r'\\?\|', link, maxsplit=1)[0].split('#', 1)[0].split('^', 1)[0].strip()
            if not target:
                continue
            if target.endswith('.md'):
                target = target[:-3]
            choices = basenames.get(target, []) if '/' not in target else ([paths[target]] if target in paths else [])
            broken = failed_names.get(target, 0) if '/' not in target else int(target in failed_stems)
            if broken and not choices:
                continue  # the page exists but failed validation; its own errors are the root cause
            if embed and not choices and PurePosixPath(target).suffix:
                # Not a note: Obsidian embeds images and PDFs by file name.
                if not attachment_exists(vault, target, attachments):
                    errors.append(f'{rel}: missing embed {target}')
                continue
            if len(choices) + broken != 1:
                errors.append(f"{rel}: {'ambiguous' if choices else 'missing'} {'embed' if embed else 'wikilink'} {target}")
            elif meta['type'] in {'area', 'note'} and choices[0]['meta']['type'] in {'gap', 'plan'}:
                errors.append(f"{rel}: spec pages must not link to the gap layer ({'embed ' if embed else ''}{target}); link from the gap to this page instead")
            else:
                edges.add((meta['id'], choices[0]['meta']['id']))
        if meta['type'] in {'area', 'note'}:
            gap_files = {n['path'].casefold() for n in notes if n['meta']['type'] in {'gap', 'plan'}} | {'gaps.md'}
            for raw in MD_LINK.findall(text) + MD_REF.findall(text):
                resolved = markdown_target(rel, raw)
                if resolved is not None and resolved.casefold() in gap_files:
                    errors.append(f"{rel}: spec pages must not link to the gap layer ({raw.strip('<>')}); link from the gap to this page instead")
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
                    if closed:
                        warnings.append(f'{rel}: missing source {source}')
                        note['stale'] = True
                        continue
                    raise ValueError('source is missing or not a file')
                if freshness:
                    old = baseline.get(meta['id'], {}).get(source)
                    data = path.read_bytes()
                    if old != hashlib.sha256(data).hexdigest():
                        mark = UNCOUNTED if old and dirty is not None and posixpath.normpath(source) in dirty else ''
                        if old and line_ending_variant(data, old):
                            warnings.append(f'{rel}: line endings differ in source {source}{mark}')
                        else:
                            note['changed'] = note['changed'] or bool(old)
                            warnings.append(f"{rel}: {'changed' if old else 'unbaselined'} source {source}{mark}")
                        note['stale'] = True
            except (OSError, ValueError) as exc:
                errors.append(f'{rel}: {source}: {exc}')
    return notes, sorted(edges), errors, warnings, baseline


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


GENERATED = '> Generated by `knowledge.py build`. Do not edit; change the source pages and rebuild.'


def esc(text):
    """Make a property value safe for one line of generated Markdown: no breaks, no raw HTML, literal backslashes."""
    return re.sub(r'\s+', ' ', str(text)).strip().replace('\\', '\\\\').replace('<', '&lt;')


def tc(text):
    """Text for a table cell."""
    return esc(text).replace('|', '\\|')


def para(text):
    """A whole line of prose that cannot turn into a heading, list, quote or fence."""
    t = esc(text)
    if re.match(r'\d+[.)]', t):
        return re.sub(r'^(\d+)([.)])', r'\1\\\2', t)
    return '\\' + t if t[:1] in '#>-+*`~|=_:[!' else t


def code(text):
    """An inline code span that survives backticks inside the text."""
    longest = max((len(run) for run in re.findall(r'`+', text)), default=0)
    mark = '`' * (longest + 1)
    return f'{mark} {text} {mark}' if longest else f'{mark}{text}{mark}'


def alias(text):
    return esc(text).translate(str.maketrans('[]|', '()/'))


def link(note):
    return f"[[{note['path'][:-3]}|{alias(note['meta']['title'])}]]"


def tlink(note):
    return link(note).replace('|', '\\|')


def rebase_target(target, folder):
    """Re-express a relative Markdown link written in folder/ so it works from the vault root."""
    bare = target[1:-1] if target.startswith('<') and target.endswith('>') else target
    path, mark, rest = re.split(r'([?#])', bare, maxsplit=1) if re.search(r'[?#]', bare) else (bare, '', '')
    if not path or path.startswith('/') or SCHEME.match(path):
        return target
    moved = posixpath.normpath(posixpath.join(folder, path)) + mark + rest
    if SCHEME.match(moved) or moved.startswith(('//', '\\', '/\\')):
        return target  # e.g. ../javascript:x or ../\\host would become a live or UNC URL once the folder part collapses
    return f'<{moved}>' if target.startswith('<') else moved


def rebase_links(line, folder):
    line = re.sub(r'(\]\()(<[^>]*>|[^\s)]*)', lambda m: m.group(1) + rebase_target(m.group(2), folder), line)
    return re.sub(r'^(\s{0,3}\[[^\]\n]+\]:\s*)(<[^>]*>|\S+)', lambda m: m.group(1) + rebase_target(m.group(2), folder), line)


SETEXT = re.compile(r'^ {0,3}(=+|-+)[ \t]*$')
NOT_PARAGRAPH = (
    re.compile(r'^(?: {4}|\t)'),                        # indented code
    re.compile(r'^ {0,3}(?:[-+*]|\d+[.)])(?:\s|$)'),    # list item
    re.compile(r'^ {0,3}(?:>|<|\|)'),                   # quote, HTML block, table row
    re.compile(r'^ {0,3}([-*_])(?: *\1){2,} *$'),       # thematic break
    re.compile(r'^ {0,3}\[[^\]\n]+\]:'),                # link reference definition
    re.compile(r'^ {0,3}(?:=+|-+)[ \t]*$'),             # another underline
)


def plain_paragraph_line(line):
    """Only unambiguous paragraph text may become Setext heading text; when unsure, leave the lines alone."""
    return bool(line.strip()) and '|' not in line and not any(r.match(line) for r in NOT_PARAGRAPH)


def neutralise_open_comment(out):
    """Rewrite an HTML comment opener that never closes (outside code) so it cannot hide what follows."""
    open_at = None
    for index, item in enumerate(out):
        if item[2]:
            continue
        masked = re.sub(r'(`+).*?\1', lambda m: ' ' * len(m.group()), item[0])
        position = 0
        while position < len(masked):
            if open_at is None:
                found = masked.find('<!--', position)
                if found < 0:
                    break
                open_at, position = (index, found), found + 4
            else:
                found = masked.find('-->', position)
                if found < 0:
                    break
                open_at, position = None, found + 3
    if open_at:
        line, column = out[open_at[0]][0], open_at[1]
        out[open_at[0]][0] = line[:column] + '&lt;!--' + line[column + 4:]


def demote(body, folder=''):
    """Drop the leading H1 and nest every other heading below ###, leaving code fences alone.

    ATX and Setext headings are both demoted. Relative Markdown links are rewritten from the
    note's folder to the vault root, where AS-BUILT.md lives. A fence or HTML comment left open
    by the note is closed or neutralised so it cannot swallow the rest of the document.
    """
    out, dropped, state = [], False, {}  # out holds [line, is_plain_paragraph_line, in_code]
    for line, in_code in lines_with_code(body, state):
        if in_code:
            out.append([line, False, True])
            continue
        line = rebase_links(line, folder)
        head = heading_of(line)
        under = SETEXT.match(line)
        if under and out and out[-1][1]:
            start = len(out)
            while start > 0 and out[start - 1][1]:
                start -= 1
            level = 1 if under.group(1)[0] == '=' else 2
            title = ' '.join(x[0].strip() for x in out[start:])
            del out[start:]
            if level == 1 and not dropped and not ''.join(x[0] for x in out).strip():
                dropped = True
                continue
            out.append(['#' * min(6, max(4, level + 2)) + ' ' + title, False, False])
            continue
        if head and not dropped and not ''.join(x[0] for x in out).strip() and head[0] == 1:
            dropped = True
            continue
        if head:
            out.append(['#' * min(6, max(4, head[0] + 2)) + (' ' + head[1] if head[1] else ''), False, False])
        else:
            out.append([line, plain_paragraph_line(line), False])
    neutralise_open_comment(out)
    lines = [x[0] for x in out]
    if state.get('fence'):
        lines.append(state['fence'][0] * state['fence'][1])
    return '\n'.join(lines).strip('\n')


def render_as_built(notes, title):
    by_id = {n['meta']['id']: n for n in notes}
    areas = sorted((n for n in notes if n['meta']['type'] == 'area'), key=lambda n: (n['meta']['title'].casefold(), n['meta']['id']))
    out = [GENERATED, '', f'# {esc(title)}: as-built specification', '',
           'How the code is implemented today. Plans, open questions and proposals live in the gap queue, not here.']
    for area in areas:
        out += ['', f"## {esc(area['meta']['title'])}"]
        if area['meta'].get('summary', '').strip():
            out += ['', para(area['meta']['summary'])]
        members = sorted((n for n in notes if n['meta']['type'] == 'note' and n['meta']['status'] != 'superseded'),
                         key=lambda n: (n['meta']['title'].casefold(), n['meta']['id']))
        for note in (n for n in members if n['meta']['areas'][0] == area['meta']['id']):
            m = note['meta']
            sources = ', '.join(code(x) for x in m['sources']) or 'none'
            out += ['', f"### {esc(m['title'])}", '', f"**id:** `{m['id']}` · **status:** {m['status']} · **updated:** {m['updated']} · **sources:** {sources}"]
            text = demote(note['body'], posixpath.dirname(note['path']))
            if text:
                out += ['', text]
        refs = [n for n in members if area['meta']['id'] in n['meta']['areas'][1:]]
        if refs:
            out.append('')
            out += [f"- See also {link(n)} (described under {esc(by_id[n['meta']['areas'][0]]['meta']['title'])})" for n in refs]
    return '\n'.join(out).rstrip('\n') + '\n'


def render_gaps(notes, title):
    by_id = {n['meta']['id']: n for n in notes}
    gaps = [n for n in notes if n['meta']['type'] == 'gap']
    plans = {}
    for n in notes:
        if n['meta']['type'] == 'plan':
            plans.setdefault(n['meta']['gap'], []).append(n)
    out = [GENERATED, '', f'# {esc(title)}: gap queue', '',
           'Derived state: needs-recheck (open and not rechecked, or recheck outdated), needs-decision (open, rechecked), otherwise the decision itself.']
    if not gaps:
        out += ['', 'No gaps recorded.']
    for state in STATE_ORDER:
        rows = sorted((g for g in gaps if g['state'] == state), key=lambda g: (g['meta']['title'].casefold(), g['meta']['id']))
        if not rows:
            continue
        out += ['', f'## {state}', '', '| Gap | Kind | Areas | Recheck | Decision | Priority | Plan |', '| --- | --- | --- | --- | --- | --- | --- |']
        for g in rows:
            m = g['meta']
            recheck = m['recheck'] if m['recheck'] == 'not-checked' else f"{RECHECK_WORDS.get(m['recheck'], m['recheck'])} ({m['rechecked_by']}, {m['rechecked_on']})"
            recheck = tc(recheck)
            if recheck_marker(g):
                recheck += ' · sources changed since'
            decision = tc(m['decision'] + (f" ({m.get('decided_by', '')}, {m.get('decided_on', '')})" if 'decided_by' in m or 'decided_on' in m else ''))
            if m['decision'] == 'duplicate' and m.get('duplicate_of') in by_id:
                decision = 'duplicate of ' + tlink(by_id[m['duplicate_of']])
            area_titles = tc(', '.join(by_id[a]['meta']['title'] for a in m['areas'] if a in by_id))
            plan = ', '.join(tlink(p) for p in sorted(plans.get(m['id'], []), key=lambda p: p['meta']['id']))
            out.append('| ' + ' | '.join(c or '-' for c in [tlink(g), tc(m['kind']), area_titles, recheck, decision,
                                                              tc(m.get('priority', '')), plan]) + ' |')
    return '\n'.join(out) + '\n'


def recheck_marker(note):
    """Automatic marker: a recorded recheck exists but a cited source's bytes changed since its fingerprint."""
    return note['meta']['recheck'] in {'confirmed', 'not-reproduced'} and bool(note.get('changed'))


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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'snapshot', 'build'])
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--vault', required=True, type=Path)
    parser.add_argument('--strict', action='store_true', help='fail check when freshness warnings exist')
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
    if args.command == 'snapshot' and not (args.all or args.notes):
        parser.error('snapshot requires --all or --notes')
    if args.command != 'snapshot' and (args.all or args.notes):
        parser.error('--all and --notes are only for snapshot')
    repo, vault = args.repo.resolve(), args.vault.resolve()
    if not repo.is_dir() or not vault.is_dir():
        parser.error('repo and vault must be existing directories')
    dirty = None
    if args.ignore_dirty:
        dirty = uncommitted_paths(repo)
        if dirty is None:
            parser.error('--ignore-dirty needs --repo to be a Git work tree')
    report = {}
    notes, edges, errors, warnings, baseline = load_vault(repo, vault, args.command != 'snapshot', dirty, report)
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
    elif args.command == 'build':
        nodes = [node_of(note) for note in notes]
        title = next((n['title'] for n in nodes if n['path'] == '00-index.md'), 'Project knowledge')
        graph = {'title': title, 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'nodes': nodes,
                 'edges': [{'source': a, 'target': b} for a, b in edges], 'warnings': warnings}
        template = (Path(__file__).resolve().parent.parent / 'assets/viewer.html').read_text(encoding='utf-8')
        if template.count('__KNOWLEDGE_DATA__') != 1:
            raise ValueError('viewer template must contain exactly one placeholder')
        serialized = json.dumps(graph, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        # Lay out each primary area as a separate, non-overlapping block.
        clusters = {}
        for node in nodes:
            area = node['id'] if node['type'] == 'area' else (node['areas'][0] if node['areas'] else '')
            clusters.setdefault(area, []).append(node)
        canvas_nodes, y = [], 0
        for area in sorted(clusters):
            group = sorted(clusters[area], key=lambda n: (n['type'] != 'area', n['path']))
            for i, node in enumerate(group):
                canvas_nodes.append({'id': node['id'], 'type': 'file', 'file': node['path'],
                                     'x': (i % 4) * 340, 'y': y + (i // 4) * 240,
                                     'width': 300, 'height': 200})
            y += ((len(group) + 3) // 4) * 240 + 80
        canvas = {'nodes': canvas_nodes, 'edges': [{'id': f'e{i}', 'fromNode': a, 'toNode': b} for i, (a, b) in enumerate(edges)]}
        for path in ('.knowledge/graph.json', 'Map.canvas', 'graph.html', 'AS-BUILT.md', 'GAPS.md'):
            output_path(vault, path)
        for entry in vault.iterdir():
            for name in GENERATED_NAMES:
                if entry.name != name and entry.name.casefold() == name.casefold():
                    raise ValueError(f'{entry.name} collides with generated {name} on a case-insensitive filesystem; rename it')
        for name in RESERVED:
            if (vault / name).is_file() and not is_generated(vault / name):
                raise ValueError(f'{name} is a hand-written page but this name is reserved for a generated file; build would overwrite it, so rename the page')
        write_json(vault / '.knowledge/graph.json', graph)
        write_json(vault / 'Map.canvas', canvas)
        atomic_write(vault / 'graph.html', template.replace('__KNOWLEDGE_DATA__', serialized))
        atomic_write(vault / 'AS-BUILT.md', render_as_built(notes, title))
        atomic_write(vault / 'GAPS.md', render_gaps(notes, title))
    uncounted = len(warnings) - len(counted)
    print(f'{args.command}: {len(notes)} notes, {len(edges)} links, {len(warnings)} warnings' + (f' ({uncounted} uncommitted, not counted)' if uncounted else ''))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
