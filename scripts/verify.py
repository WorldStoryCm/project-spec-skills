#!/usr/bin/env python3
"""Run local, read-only checks for the skill bundles and fictional example."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / 'skills/project-knowledge'
EXAMPLE = ROOT / 'examples/parcel-desk'
VAULT = EXAMPLE / 'knowledge/parcel-desk'
SKILLS = ('project-knowledge', 'spec-audit', 'spec-change', 'spec-investigation', 'spec-plan')
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def run(label, command, cwd=ROOT):
    print(f'\n{label}:', flush=True)
    result = subprocess.run(command, cwd=cwd, check=False, env=ENV)
    print(f'{"PASS" if result.returncode == 0 else "FAIL"}: {label} (exit {result.returncode})', flush=True)
    return result.returncode == 0


def frontmatter():
    errors = []
    for name in SKILLS:
        path = ROOT / 'skills' / name / 'SKILL.md'
        try:
            content = path.read_text(encoding='utf-8')
            match = re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|$)', content, re.S)
            if not match:
                raise ValueError('missing frontmatter')
            fields = {}
            for line in match.group(1).splitlines():
                key, sep, value = line.partition(':')
                if not sep or key in fields:
                    raise ValueError('invalid or duplicate frontmatter field')
                fields[key] = value.strip().strip('"\'')
            if fields.get('name') != name or len(fields.get('name', '')) > 64:
                raise ValueError('name must match directory and be at most 64 characters')
            description = fields.get('description', '')
            if not description or len(description) > 1024:
                raise ValueError('description must be nonempty and at most 1024 characters')
            if fields.get('license') != 'MIT':
                raise ValueError('license must be MIT')
            if (path.parent / 'LICENSE').read_bytes() != (ROOT / 'LICENSE').read_bytes():
                raise ValueError('installable skill must retain the full MIT notice')
        except (OSError, ValueError) as exc:
            errors.append(f'{path.relative_to(ROOT)}: {exc}')
    return errors


def without_code(text):
    # Remove fenced blocks and inline code before looking for ordinary Markdown links.
    # CommonMark: a backtick opener's info string cannot contain a backtick, and a closer has no info string.
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is None:
            if match and not (match.group(1)[0] == '`' and '`' in match.group(2)):
                fence = (match.group(1)[0], len(match.group(1)))
            else:
                lines.append(re.sub(r'(`+).*?\1', '', line))
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1] and not match.group(2).strip():
            fence = None
    return '\n'.join(lines)


def links():
    errors = []
    for path in sorted(ROOT.rglob('*.md')):
        if any(part in {'.git', '__pycache__', 'node_modules'} for part in path.relative_to(ROOT).parts):
            continue
        text = without_code(path.read_text(encoding='utf-8'))
        inline = re.findall(r'(?<!!)\[[^\]\n]+\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)', text)
        references = re.findall(r'^\s{0,3}\[[^\]\n]+\]:\s*(<[^>]+>|[^\s]+)', text, re.M)
        for raw in inline + references:
            target = raw.strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            local = (path.parent / unquote(parsed.path)).resolve()
            if not local.exists():
                errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    return errors


def normalized_graph(path):
    graph = json.loads(path.read_text(encoding='utf-8'))
    graph.pop('generatedAt', None)
    return graph


def check_generated():
    with tempfile.TemporaryDirectory(prefix='verify-knowledge-') as directory:
        copy = Path(directory) / 'vault'
        shutil.copytree(VAULT, copy)
        command = [sys.executable, str(KNOWLEDGE / 'scripts/knowledge.py'), 'build',
                   '--repo', str(EXAMPLE), '--vault', str(copy)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False, env=ENV)
        if result.returncode:
            return [f'temporary build failed (exit {result.returncode}): {result.stderr.strip()}']
        errors = []
        expected_graph = normalized_graph(copy / '.knowledge/graph.json')
        if normalized_graph(VAULT / '.knowledge/graph.json') != expected_graph:
            errors.append('graph.json differs from current notes and links')
        for name in ('graph.html', 'Map.canvas'):
            if (VAULT / name).exists():
                errors.append(f'{name} is no longer generated; delete it from the example vault')
        for name in ('AS-BUILT.md', 'GAPS.md'):
            shipped = VAULT / name
            if not shipped.is_file():
                errors.append(f'{name} is missing from the example vault; run build')
            elif shipped.read_bytes() != (copy / name).read_bytes():
                errors.append(f'{name} differs from the generated copy; run build')
        return errors


GAP_RULES = KNOWLEDGE / 'references/gaps.md'
GAP_RULE_COPIES = tuple(ROOT / 'skills' / name / 'references/gaps.md' for name in ('spec-audit', 'spec-change', 'spec-investigation', 'spec-plan'))


def check_gap_rules():
    if not GAP_RULES.is_file():
        return [f'{GAP_RULES.relative_to(ROOT)} is missing (it is the canonical gap rules file)']
    canonical = GAP_RULES.read_bytes()
    errors = []
    for copy in GAP_RULE_COPIES:
        if not copy.is_file():
            errors.append(f'{copy.relative_to(ROOT)} is missing; copy it from {GAP_RULES.relative_to(ROOT)}')
        elif copy.read_bytes() != canonical:
            errors.append(f'{copy.relative_to(ROOT)} differs from {GAP_RULES.relative_to(ROOT)}; copy it byte for byte')
    return errors


def stage(label, check):
    try:
        errors = check()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(f'  {error}')
    print(f'{"FAIL" if errors else "PASS"}: {label}', flush=True)
    return not errors


def node_check():
    node = shutil.which('node')
    if not node:
        print('NOT RUN: viewer syntax, inline rendering and the package command (optional; Node not installed)', flush=True)
        return True
    html = (KNOWLEDGE / 'assets/viewer.html').read_text(encoding='utf-8')
    scripts = re.findall(r'<script>\s*(.*?)\s*</script>', html, re.S)
    if len(scripts) != 1:
        print('FAIL: viewer JavaScript syntax (expected one executable script)', flush=True)
        return False
    with tempfile.TemporaryDirectory(prefix='verify-viewer-') as directory:
        script = Path(directory) / 'viewer.js'
        script.write_text(scripts[0], encoding='utf-8')
        syntax = run('viewer JavaScript syntax', [node, '--check', str(script)])
        rendering = run('viewer inline rendering', [node, str(ROOT / 'scripts/test_viewer.cjs')])
        package = run('package command', [node, str(ROOT / 'scripts/test_cli.cjs')])
        return syntax and rendering and package


def main():
    results = [stage('skill frontmatter', frontmatter), stage('local Markdown links', links)]
    results.append(run('knowledge helper tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(KNOWLEDGE / 'scripts'), '-p', 'test_*.py']))
    results.append(run('fictional fixture tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'], cwd=EXAMPLE))
    results.append(run('strict vault check', [sys.executable, str(KNOWLEDGE / 'scripts/knowledge.py'), 'check', '--strict', '--repo', str(EXAMPLE), '--vault', str(VAULT)]))
    results.append(stage('generated graph artifacts', check_generated))
    results.append(stage('gap rules copies', check_gap_rules))
    try:
        results.append(node_check())
    except OSError as exc:
        print(f'FAIL: viewer JavaScript syntax: {exc}', flush=True)
        results.append(False)
    print(f'\n{"PASS" if all(results) else "FAIL"}: verification', flush=True)
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
