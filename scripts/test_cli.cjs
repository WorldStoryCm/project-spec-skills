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
  assert.deepEqual(skills, ['project-knowledge', 'spec-change']);
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
  assert.equal((r.out.match(/installed to/g) || []).length, 2);
  for (const name of skills) assert.ok(fs.existsSync(path.join(claude, name, 'SKILL.md')), name);
  assert.equal(read(path.join(claude, 'project-knowledge/scripts/knowledge.py')), read(path.join(ROOT, 'skills/project-knowledge/scripts/knowledge.py')));
  assert.ok(!fs.existsSync(path.join(claude, 'project-knowledge/scripts/__pycache__')));
  // a copy holds what writing a spec needs: the instructions and the helpers, no viewer page and no tests
  assert.ok(!fs.existsSync(path.join(claude, 'project-knowledge/assets')));
  assert.deepEqual(fs.readdirSync(path.join(claude, 'project-knowledge/scripts')).sort(), ['coverage.py', 'knowledge.py', 'maintain.py', 'merge.py']);
  const marker = JSON.parse(read(path.join(claude, 'spec-change/.project-spec.json')));
  assert.equal(marker.version, VERSION);
  assert.deepEqual(Object.keys(marker.files).sort(), ['LICENSE', 'SKILL.md', 'agents/openai.yaml', 'references/gaps.md', 'references/plan.md']);
  r = run(['install', '--dir', 'knowledge/tooling', '--skills', 'project-knowledge']);
  assert.equal(r.code, 0, r.err);
  assert.deepEqual(fs.readdirSync(tooling), ['project-knowledge']);

  // status sees the home copies and the project copy, and says what is missing
  r = run(['status']);
  assert.ok(r.out.includes('~/.claude/skills') && r.out.includes(tooling), r.out);
  assert.ok(!r.out.includes('.codex'));
  assert.ok(r.out.includes('Everything installed is current.'));
  assert.ok(/knowledge\/tooling\n  project-knowledge: current\n  spec-change: not installed/.test(r.out), r.out);
  assert.ok(run(['install', '--claude']).out.includes('already current'));

  // an older copy is refreshed; a file this version dropped is removed, a file of yours is kept
  const change = path.join(claude, 'spec-change');
  const old = JSON.parse(read(path.join(change, '.project-spec.json')));
  const sha = value => require('node:crypto').createHash('sha256').update(value).digest('hex');
  fs.writeFileSync(path.join(change, 'retired.md'), 'old');
  fs.writeFileSync(path.join(change, 'mine.md'), 'keep me');
  fs.writeFileSync(path.join(change, 'SKILL.md'), 'older text');
  old.version = '0.1.0';
  old.files['retired.md'] = sha('old');
  old.files['SKILL.md'] = sha('older text');
  fs.writeFileSync(path.join(change, '.project-spec.json'), JSON.stringify(old));
  assert.ok(run(['status']).out.includes('spec-change: older (0.1.0)'));
  assert.ok(run(['status']).out.includes('1 to refresh: project-spec update'));
  r = run(['update']);
  assert.equal(r.code, 0, r.out + r.err);
  assert.ok(r.out.includes(`spec-change: updated to ${VERSION}`));
  assert.ok(!fs.existsSync(path.join(change, 'retired.md')));
  assert.equal(read(path.join(change, 'mine.md')), 'keep me');
  assert.equal(read(path.join(change, 'SKILL.md')), read(path.join(ROOT, 'skills/spec-change/SKILL.md')));
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

  // copies made by hand before this command existed: adopted when identical, backed up when not;
  // a skill this version no longer has is removed, with its files kept
  fs.cpSync(path.join(ROOT, 'skills/spec-change'), path.join(codex, 'spec-change'), { recursive: true });
  fs.cpSync(path.join(ROOT, 'skills/project-knowledge'), path.join(codex, 'project-knowledge'), { recursive: true });
  fs.writeFileSync(path.join(codex, 'project-knowledge/SKILL.md'), 'something older');
  for (const [folder, name] of [['spec-audit', 'spec-audit'], ['spec-plan', 'spec-plan'], ['spec-investigation', 'somebody-elses-skill']]) {
    fs.mkdirSync(path.join(codex, folder), { recursive: true });
    fs.writeFileSync(path.join(codex, folder, 'SKILL.md'), `---\nname: ${name}\ndescription: old\n---\n\nold skill\n`);
  }
  r = run(['status']);
  assert.ok(/\.codex\/skills\n  project-knowledge: differs, no version recorded\n  spec-change: current\n  spec-audit: retired, update removes it\n  spec-plan: retired, update removes it\n/.test(r.out), r.out);
  assert.ok(r.out.includes('3 to refresh: project-spec update'), r.out);
  r = run(['update']);
  assert.equal(r.code, 0, r.out + r.err);
  assert.ok(r.out.includes('spec-change: recorded as current'));
  assert.ok(/project-knowledge: updated to .*the old copy is in/.test(r.out), r.out);
  const gone = /spec-audit: removed, this skill is retired; the old copy is in (~\/\.project-spec\/backups\/\S+)/.exec(r.out);
  assert.ok(gone, r.out);
  assert.ok(read(path.join(home, gone[1].slice(2), 'SKILL.md')).includes('old skill'));
  assert.ok(!fs.existsSync(path.join(codex, 'spec-audit')) && !fs.existsSync(path.join(codex, 'spec-plan')));
  assert.ok(fs.existsSync(path.join(codex, 'spec-investigation/SKILL.md')), 'a folder that only shares the name is somebody else\'s');
  assert.ok(fs.existsSync(path.join(codex, 'spec-change/.project-spec.json')));
  assert.ok(run(['status']).out.includes('Everything installed is current.'));
  // update adds nothing new
  fs.rmSync(path.join(claude, 'spec-change'), { recursive: true });
  r = run(['update']);
  assert.ok(r.out.includes('Not installed there, so left out:') && r.out.includes('~/.claude/skills/spec-change'), r.out);
  assert.ok(!fs.existsSync(path.join(claude, 'spec-change')));

  // the viewer goes into a copy only when asked, stays in a copy that has it, and comes out when asked
  const lean = path.join(project, 'lean');
  const page = path.join(lean, 'project-knowledge/assets/viewer.html');
  const example = path.join(ROOT, 'examples/parcel-desk');
  const helper = (...args) => spawnSync(process.platform === 'win32' ? 'python' : 'python3', [path.join(lean, 'project-knowledge/scripts/knowledge.py'), ...args, '--repo', example], { encoding: 'utf8' });
  assert.equal(run(['install', '--dir', lean, '--with-viewer', '--no-viewer']).code, 2);
  r = run(['install', '--dir', lean, '--skills', 'project-knowledge']);
  assert.ok(r.out.includes(`installed to ${VERSION}`) && !r.out.includes('with the viewer'), r.out);
  let built = helper('build', '--out', path.join(temp, 'lean.html'));
  assert.equal(built.status, 2, built.stderr);
  assert.ok(built.stderr.includes('the viewer is not part of this copy of the skill') && built.stderr.includes('npx project-spec serve'), built.stderr);
  assert.equal(helper('check').status, 0, 'a copy without the viewer still checks a vault');
  r = run(['install', '--dir', lean, '--skills', 'project-knowledge', '--with-viewer']);
  assert.ok(r.out.includes(`updated to ${VERSION}, with the viewer`), r.out);
  assert.equal(read(page), read(path.join(ROOT, 'viewer/viewer.html')));
  built = helper('build', '--out', path.join(temp, 'lean.html'));
  assert.equal(built.status, 0, built.stderr);
  assert.ok(read(path.join(temp, 'lean.html')).includes('Parcel Desk'));
  // a copy an earlier version made: it has the viewer and the helper tests; update keeps the first and removes the second
  const before = JSON.parse(read(path.join(lean, 'project-knowledge/.project-spec.json')));
  fs.writeFileSync(path.join(lean, 'project-knowledge/scripts/test_knowledge.py'), 'old test');
  fs.writeFileSync(page, 'old viewer');
  before.version = '0.9.2';
  before.files['scripts/test_knowledge.py'] = sha('old test');
  before.files['assets/viewer.html'] = sha('old viewer');
  fs.writeFileSync(path.join(lean, 'project-knowledge/.project-spec.json'), JSON.stringify(before));
  const inLean = { cwd: project };
  fs.mkdirSync(path.join(project, '.agents/skills'), { recursive: true });
  fs.renameSync(path.join(lean, 'project-knowledge'), path.join(project, '.agents/skills/project-knowledge'));
  const agents = path.join(project, '.agents/skills/project-knowledge');
  assert.ok(run(['status'], inLean).out.includes('project-knowledge: older (0.9.2), with the viewer'), run(['status'], inLean).out);
  r = run(['update'], inLean);
  assert.ok(r.out.includes(`.agents/skills/project-knowledge: updated to ${VERSION}, with the viewer`), r.out);
  assert.equal(read(path.join(agents, 'assets/viewer.html')), read(path.join(ROOT, 'viewer/viewer.html')));
  assert.ok(!fs.existsSync(path.join(agents, 'scripts/test_knowledge.py')));
  r = run(['install', '--dir', path.join(project, '.agents/skills'), '--skills', 'project-knowledge', '--no-viewer']);
  assert.ok(r.out.includes(`updated to ${VERSION}`) && !r.out.includes('with the viewer'), r.out);
  assert.ok(!fs.existsSync(path.join(agents, 'assets')));
  assert.ok(run(['status'], inLean).out.includes('Everything installed is current.'));
  fs.rmSync(path.join(project, '.agents'), { recursive: true });

  // the helpers are started from the package, in the current folder by default
  const dry = { env: { PROJECT_SPEC_DRY_RUN: '1', PROJECT_SPEC_PYTHON: 'py' } };
  const script = path.join(ROOT, 'skills/project-knowledge/scripts');
  assert.equal(run(['serve'], dry).out.trim(), `py ${script}/knowledge.py serve --repo . --open`);
  assert.equal(run(['serve', '--no-open', '--port', '9000', '--repo', 'x'], dry).out.trim(), `py ${script}/knowledge.py serve --port 9000 --repo x`);
  assert.equal(run(['build', '--out', 'site/spec.html'], dry).out.trim(), `py ${script}/knowledge.py build --out site/spec.html --repo .`);
  assert.equal(run(['check', '--strict'], dry).out.trim(), `py ${script}/knowledge.py check --strict --repo .`);
  assert.equal(run(['scan', '--write-status'], dry).out.trim(), `py ${script}/maintain.py scan --write-status --repo .`);
  assert.equal(run(['coverage', '--path', 'src/chat'], dry).out.trim(), `py ${script}/coverage.py --path src/chat --repo .`);
  r = run(['check'], { cwd: path.join(ROOT, 'examples/parcel-desk') });
  assert.equal(r.code, 0, r.err);
  assert.ok(/check: \d+ notes/.test(r.out), r.out);
  assert.equal(run(['check'], { env: { PROJECT_SPEC_PYTHON: 'no-such-python-anywhere' } }).code, 2);

  // the Claude Code plugin manifest names the same version, and the marketplace lists that plugin
  const pkg = JSON.parse(read(path.join(ROOT, 'package.json')));
  const plugin = JSON.parse(read(path.join(ROOT, '.claude-plugin/plugin.json')));
  const market = JSON.parse(read(path.join(ROOT, '.claude-plugin/marketplace.json')));
  assert.equal(plugin.version, pkg.version, 'plugin.json and package.json name different versions');
  assert.deepEqual(market.plugins.map(p => [p.name, p.source]), [[plugin.name, './']]);
  assert.equal(Object.keys(pkg.bin).join(), 'project-spec');

  // what goes to the npm registry: the command and the skills, and nothing a local run left behind
  const npm = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['pack', '--dry-run', '--json', '--ignore-scripts'], { cwd: ROOT, encoding: 'utf8' });
  if (npm.status === 0) {
    const packed = JSON.parse(npm.stdout)[0].files.map(f => f.path);
    for (const needed of ['bin/project-spec.mjs', 'README.md', 'LICENSE', ...skills.map(n => `skills/${n}/SKILL.md`), 'viewer/viewer.html'])
      assert.ok(packed.includes(needed), `the package lacks ${needed}`);
    const stray = packed.filter(f => /__pycache__|\.pyc$|^examples\/|^docs\/|^scripts\/|^tests\/|\/test_[^/]*\.py$|^skills\/.*\.html$/.test(f));
    assert.deepEqual(stray, [], 'the package carries files it should not');
  } else console.log('NOT RUN: package contents (npm not available)');

  console.log('PASS: package command installs, updates, reports and starts the helpers');
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
