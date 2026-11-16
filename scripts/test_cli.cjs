// Checks for the project-spec command; run with Node, no dependencies.
// Everything happens under a temporary HOME and a temporary project folder.
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const CLI = path.join(ROOT, 'bin/project-spec.mjs');
const VERSION = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version;
const temp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'project-spec-cli-')));
const home = path.join(temp, 'home');
const project = path.join(temp, 'project');
fs.mkdirSync(home);
fs.mkdirSync(project);

function run(args, { cwd = project, env = {} } = {}) {
  const result = spawnSync(process.execPath, [CLI, ...args], { cwd, encoding: 'utf8', env: { ...process.env, HOME: home, USERPROFILE: home, ...env } });
  return { code: result.status, out: result.stdout, err: result.stderr };
}
const skills = fs.readdirSync(path.join(ROOT, 'skills')).filter(n => fs.existsSync(path.join(ROOT, 'skills', n, 'SKILL.md'))).sort();
const claude = path.join(home, '.claude/skills');
const codex = path.join(home, '.codex/skills');
const tooling = path.join(project, 'knowledge/tooling');
const read = file => fs.readFileSync(file, 'utf8');

try {
  assert.deepEqual(skills, ['project-knowledge', 'spec-audit', 'spec-change', 'spec-investigation', 'spec-plan']);
  assert.equal(run(['version']).out.trim(), VERSION);
  assert.ok(run([]).out.includes('project-spec install'));
  assert.equal(run(['nonsense']).code, 2);

  // nothing installed yet
  assert.ok(run(['status']).out.includes('No copies found.'));
  assert.equal(run(['update']).code, 2);
  assert.equal(run(['install']).code, 2, 'install does not guess where');
  assert.ok(run(['install', '--skills', 'nope', '--claude']).err.includes('no such skill: nope'));

  // install everything for one agent, one skill into the project
  let r = run(['install', '--claude']);
  assert.equal(r.code, 0, r.err);
  assert.equal((r.out.match(/installed to/g) || []).length, 5);
  for (const name of skills) assert.ok(fs.existsSync(path.join(claude, name, 'SKILL.md')), name);
  assert.equal(read(path.join(claude, 'project-knowledge/scripts/knowledge.py')), read(path.join(ROOT, 'skills/project-knowledge/scripts/knowledge.py')));
  assert.ok(!fs.existsSync(path.join(claude, 'project-knowledge/scripts/__pycache__')));
  const marker = JSON.parse(read(path.join(claude, 'spec-plan/.project-spec.json')));
  assert.equal(marker.version, VERSION);
  assert.deepEqual(Object.keys(marker.files).sort(), ['LICENSE', 'SKILL.md', 'agents/openai.yaml', 'references/gaps.md']);
  r = run(['install', '--dir', 'knowledge/tooling', '--skills', 'project-knowledge']);
  assert.equal(r.code, 0, r.err);
  assert.deepEqual(fs.readdirSync(tooling), ['project-knowledge']);

  // status sees the home copies and the project copy, and says what is missing
  r = run(['status']);
  assert.ok(r.out.includes('~/.claude/skills') && r.out.includes(tooling), r.out);
  assert.ok(!r.out.includes('.codex'));
  assert.ok(r.out.includes('Everything installed is current.'));
  assert.ok(/knowledge\/tooling\n  project-knowledge: current\n  spec-audit: not installed/.test(r.out), r.out);
  assert.ok(run(['install', '--claude']).out.includes('already current'));

  // an older copy is refreshed; a file this version dropped is removed, a file of yours is kept
  const plan = path.join(claude, 'spec-plan');
  const old = JSON.parse(read(path.join(plan, '.project-spec.json')));
  fs.writeFileSync(path.join(plan, 'retired.md'), 'old');
  fs.writeFileSync(path.join(plan, 'mine.md'), 'keep me');
  fs.writeFileSync(path.join(plan, 'SKILL.md'), 'older text');
  old.version = '0.1.0';
  old.files['retired.md'] = require('node:crypto').createHash('sha256').update('old').digest('hex');
  old.files['SKILL.md'] = require('node:crypto').createHash('sha256').update('older text').digest('hex');
  fs.writeFileSync(path.join(plan, '.project-spec.json'), JSON.stringify(old));
  assert.ok(run(['status']).out.includes('spec-plan: older (0.1.0)'));
  assert.ok(run(['status']).out.includes('1 to refresh: project-spec update'));
  r = run(['update']);
  assert.equal(r.code, 0, r.out + r.err);
  assert.ok(r.out.includes(`spec-plan: updated to ${VERSION}`));
  assert.ok(!fs.existsSync(path.join(plan, 'retired.md')));
  assert.equal(read(path.join(plan, 'mine.md')), 'keep me');
  assert.equal(read(path.join(plan, 'SKILL.md')), read(path.join(ROOT, 'skills/spec-plan/SKILL.md')));
  assert.ok(run(['status']).out.includes('Everything installed is current.'));

  // a copy edited by hand is not replaced, unless forced, and then the old files are kept
  fs.appendFileSync(path.join(tooling, 'project-knowledge/SKILL.md'), '\nmy note\n');
  assert.ok(run(['status']).out.includes('project-knowledge: edited by hand: SKILL.md'));
  r = run(['update']);
  assert.equal(r.code, 1);
  assert.ok(r.out.includes('NOT updated, edited by hand (SKILL.md); pass --force'));
  assert.ok(read(path.join(tooling, 'project-knowledge/SKILL.md')).endsWith('my note\n'));
  r = run(['update', '--force']);
  assert.equal(r.code, 0, r.out + r.err);
  const kept = /the old copy is in (~\/\.project-spec\/backups\/\S+)/.exec(r.out);
  assert.ok(kept, r.out);
  assert.ok(read(path.join(home, kept[1].slice(2), 'SKILL.md')).endsWith('my note\n'));
  assert.equal(read(path.join(tooling, 'project-knowledge/SKILL.md')), read(path.join(ROOT, 'skills/project-knowledge/SKILL.md')));

  // a copy made by hand before this command existed: adopted when identical, backed up when not
  fs.cpSync(path.join(ROOT, 'skills/spec-audit'), path.join(codex, 'spec-audit'), { recursive: true });
  fs.cpSync(path.join(ROOT, 'skills/spec-plan'), path.join(codex, 'spec-plan'), { recursive: true });
  fs.writeFileSync(path.join(codex, 'spec-plan/SKILL.md'), 'something older');
  r = run(['status']);
  assert.ok(/\.codex\/skills\n  project-knowledge: not installed\n  spec-audit: current\n  spec-change: not installed\n  spec-investigation: not installed\n  spec-plan: differs, no version recorded/.test(r.out), r.out);
  r = run(['update']);
  assert.equal(r.code, 0, r.out + r.err);
  assert.ok(r.out.includes('spec-audit: recorded as current'));
  assert.ok(/spec-plan: updated to .*the old copy is in/.test(r.out), r.out);
  assert.ok(r.out.includes('Not installed there, so left out:') && r.out.includes('~/.codex/skills/spec-change'));
  assert.ok(!fs.existsSync(path.join(codex, 'spec-change')), 'update adds nothing new');
  assert.ok(fs.existsSync(path.join(codex, 'spec-audit/.project-spec.json')));

  // the helpers are started from the package, in the current folder by default
  const dry = { env: { PROJECT_SPEC_DRY_RUN: '1', PROJECT_SPEC_PYTHON: 'py' } };
  const script = path.join(ROOT, 'skills/project-knowledge/scripts');
  assert.equal(run(['serve'], dry).out.trim(), `py ${script}/knowledge.py serve --repo . --open`);
  assert.equal(run(['serve', '--no-open', '--port', '9000', '--repo', 'x'], dry).out.trim(), `py ${script}/knowledge.py serve --port 9000 --repo x`);
  assert.equal(run(['check', '--strict'], dry).out.trim(), `py ${script}/knowledge.py check --strict --repo .`);
  assert.equal(run(['scan', '--write-status'], dry).out.trim(), `py ${script}/maintain.py scan --write-status --repo .`);
  r = run(['check'], { cwd: path.join(ROOT, 'examples/parcel-desk') });
  assert.equal(r.code, 0, r.err);
  assert.ok(/check: \d+ notes/.test(r.out), r.out);
  assert.equal(run(['check'], { env: { PROJECT_SPEC_PYTHON: 'no-such-python-anywhere' } }).code, 2);

  console.log('PASS: package command installs, updates, reports and starts the helpers');
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
