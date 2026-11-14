#!/usr/bin/env python3
"""Validate and build a project-knowledge vault using only the standard library."""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

TYPES = {'index', 'area', 'note', 'gap', 'run'}
STATUSES = {'current', 'partial', 'planned', 'unverified', 'conflict', 'stale', 'superseded'}
ARRAYS = {'areas', 'sources', 'tags', 'aliases', 'task_ids'}
STRINGS = {'id', 'title', 'type', 'status', 'updated', 'summary', 'verification'}
REQUIRED = {'id', 'title', 'type', 'status', 'areas', 'sources', 'updated'}
LINK = re.compile(r'(?<!!)\[\[([^\]\n]+)\]\]')


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


def credential_path(value):
    parts = [p.lower() for p in PurePosixPath(value).parts]
    return any(p in {'.env', '.aws', '.ssh', '.gnupg', 'credentials', 'secrets'} or
               p.startswith('.env.') or p.endswith(('.pem', '.key', '.p12', '.pfx')) for p in parts)


def prose(body):
    lines, fence = [], None
    for line in body.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if match:
            mark = match.group(1)
            if fence is None:
                fence = (mark[0], len(mark))
            elif mark[0] == fence[0] and len(mark) >= fence[1]:
                fence = None
            continue
        if fence is None:
            lines.append(re.sub(r'(`+).*?\1', '', line))
    return '\n'.join(lines)


def load_vault(repo, vault, freshness=True):
    errors, warnings, notes = [], [], []
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
        try:
            safe_path(vault, rel)
            content = file.read_text(encoding='utf-8')
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
            missing = REQUIRED - meta.keys()
            if missing:
                raise ValueError('missing properties: ' + ', '.join(sorted(missing)))
            for key in STRINGS & meta.keys():
                if not isinstance(meta[key], str):
                    raise ValueError(f'{key} must be a string')
            for key in ARRAYS & meta.keys():
                if not isinstance(meta[key], list) or any(not isinstance(x, str) for x in meta[key]):
                    raise ValueError(f'{key} must be a string array')
            if not re.fullmatch(r'[a-z0-9-]+', meta['id']):
                raise ValueError('invalid id')
            if not meta['title'].strip() or meta['type'] not in TYPES or meta['status'] not in STATUSES:
                raise ValueError('invalid title, type or status')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', meta['updated']):
                raise ValueError('updated must be YYYY-MM-DD')
            dt.date.fromisoformat(meta['updated'])
            if meta['type'] in {'note', 'gap'} and not meta['areas']:
                raise ValueError('note or gap requires an area')
            if meta['type'] == 'note' and meta['status'] == 'current' and not meta['sources']:
                raise ValueError('current note requires sources')
            notes.append({'meta': meta, 'path': rel, 'body': content[match.end():]})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f'{rel}: {exc}')
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
    edges = set()
    for note in notes:
        meta, rel = note['meta'], note['path']
        note['stale'] = False
        for area in meta['areas']:
            if area not in area_ids:
                errors.append(f'{rel}: unknown area {area}')
            elif area != meta['id']:
                edges.add((area, meta['id']))
        for link in LINK.findall(prose(note['body'])):
            target = link.split('|', 1)[0].split('#', 1)[0].split('^', 1)[0].strip()
            if not target:
                continue
            if target.endswith('.md'):
                target = target[:-3]
            choices = basenames.get(target, []) if '/' not in target else ([paths[target]] if target in paths else [])
            if len(choices) != 1:
                errors.append(f"{rel}: {'ambiguous' if choices else 'missing'} wikilink {target}")
            else:
                edges.add((meta['id'], choices[0]['meta']['id']))
        for source in meta['sources']:
            try:
                if credential_path(source):
                    raise ValueError('credential source is forbidden')
                path = safe_path(repo, source)
                if credential_path(path.resolve().relative_to(repo).as_posix()):
                    raise ValueError('credential source is forbidden')
                if not path.is_file():
                    if meta['status'] in {'stale', 'superseded'}:
                        warnings.append(f'{rel}: missing source {source}')
                        note['stale'] = True
                        continue
                    raise ValueError('source is missing or not a file')
                if freshness:
                    old = baseline.get(meta['id'], {}).get(source)
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    if old != digest:
                        warnings.append(f"{rel}: {'changed' if old else 'unbaselined'} source {source}")
                        note['stale'] = True
            except (OSError, ValueError) as exc:
                errors.append(f'{rel}: {source}: {exc}')
    return notes, sorted(edges), errors, warnings, baseline


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'snapshot', 'build'])
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--vault', required=True, type=Path)
    parser.add_argument('--strict', action='store_true', help='fail check when freshness warnings exist')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true')
    group.add_argument('--notes', nargs='+')
    args = parser.parse_args(argv)
    if args.strict and args.command != 'check':
        parser.error('--strict is only for check')
    if args.command == 'snapshot' and not (args.all or args.notes):
        parser.error('snapshot requires --all or --notes')
    if args.command != 'snapshot' and (args.all or args.notes):
        parser.error('--all and --notes are only for snapshot')
    repo, vault = args.repo.resolve(), args.vault.resolve()
    if not repo.is_dir() or not vault.is_dir():
        parser.error('repo and vault must be existing directories')
    notes, edges, errors, warnings, baseline = load_vault(repo, vault, args.command != 'snapshot')
    if args.command == 'snapshot' and args.notes:
        missing = set(args.notes) - {n['meta']['id'] for n in notes}
        if missing:
            errors.append('Unknown note IDs: ' + ', '.join(sorted(missing)))
    for message in errors:
        print('ERROR:', message, file=sys.stderr)
    for message in warnings:
        print('WARNING:', message, file=sys.stderr)
    if errors or (args.strict and warnings):
        return 1
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
        nodes = []
        for note in notes:
            m = note['meta']
            nodes.append({k: m[k] for k in ('id', 'title', 'type', 'status', 'areas', 'sources', 'updated')} | {
                'tags': m.get('tags', []), 'path': note['path'], 'body': note['body'],
                'summary': m.get('summary', ''), 'stale': note['stale']})
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
        for path in ('.knowledge/graph.json', 'Map.canvas', 'graph.html'):
            output_path(vault, path)
        write_json(vault / '.knowledge/graph.json', graph)
        write_json(vault / 'Map.canvas', canvas)
        (vault / 'graph.html').write_text(template.replace('__KNOWLEDGE_DATA__', serialized), encoding='utf-8')
    print(f'{args.command}: {len(notes)} notes, {len(edges)} links, {len(warnings)} warnings')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
