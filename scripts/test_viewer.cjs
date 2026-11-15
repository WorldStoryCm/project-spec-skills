// DOM-stub checks for the offline viewer; run with Node, no dependencies.
// The viewer's real script runs against a tiny fake DOM, so these checks
// exercise the shipped code (Markdown rendering, Spec/Gaps modes, state
// derivation, legacy payloads), not a copy of it.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../skills/project-knowledge/assets/viewer.html'), 'utf8');
const scriptStart = template.lastIndexOf('<script>');
const scriptEnd = template.lastIndexOf('</script>');
assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, 'viewer script must exist');
const script = template.slice(scriptStart + '<script>'.length, scriptEnd);

// --- static guarantees -----------------------------------------------------
assert.equal(template.split('__KNOWLEDGE_DATA__').length - 1, 1, 'exactly one data placeholder');
assert.ok(!/<script[^>]+\bsrc=|<link[^>]+\bhref=|\bfetch\(|XMLHttpRequest|\.innerHTML|insertAdjacentHTML|outerHTML/.test(template),
  'no external loads or raw HTML injection');

// --- fake DOM --------------------------------------------------------------
class FakeEl {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attrs = {};
    this.dataset = {};
    this.listeners = {};
    this.style = {};
    this.className = '';
    this.hidden = false;
    this.value = '';
  }
  get tag() { return this.tagName.toLowerCase(); }
  get textContent() { return this.children.map(c => (c.text !== undefined ? c.text : c.textContent)).join(''); }
  set textContent(v) { this.children = [{ text: String(v) }]; }
  get lastChild() { return this.children[this.children.length - 1]; }
  append(...nodes) { for (const n of nodes) this.children.push(typeof n === 'string' ? { text: n } : n); }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  fire(type, event = {}) { (this.listeners[type] || []).forEach(fn => fn({ preventDefault() {}, ...event })); }
  click() { this.fire('click'); }
}
function walk(root, visit) {
  for (const c of root.children) {
    if (c instanceof FakeEl) { visit(c); walk(c, visit); }
  }
}
function findAll(root, pred) { const out = []; walk(root, e => { if (pred(e)) out.push(e); }); return out; }
function cls(e) { return String(e.className || e.attrs.class || ''); }

function load(payload) {
  const registry = new Map();
  const body = new FakeEl('body');
  const document = {
    body,
    baseURI: 'file:///vault/graph.html',
    title: '',
    createElement: tag => new FakeEl(tag),
    createElementNS: (ns, tag) => new FakeEl(tag),
    createTextNode: text => ({ text }),
    getElementById: () => ({ textContent: JSON.stringify(payload) }),
    querySelector(sel) {
      if (!registry.has(sel)) registry.set(sel, new FakeEl('div'));
      return registry.get(sel);
    },
    querySelectorAll: () => [],
  };
  const ctx = vm.createContext({ document, URL, Map, Set });
  vm.runInContext(script, ctx);
  const q = sel => document.querySelector(sel);
  const view = {
    q,
    body,
    mode: () => body.dataset.mode,
    items: () => findAll(q('#list'), e => cls(e).split(' ').includes('item')),
    itemTitles: () => view.items().map(e => findAll(e, x => x.tag === 'strong')[0].textContent),
    navTitles: () => findAll(q('#nav-list'), e => cls(e).split(' ').includes('item')).map(e => findAll(e, x => x.tag === 'strong')[0].textContent),
    graphLabels: () => findAll(q('#graph'), e => e.attrs.role === 'button').map(e => e.attrs['aria-label']),
    graphNode: label => findAll(q('#graph'), e => e.attrs['aria-label'] === label)[0],
    buttons: (root, text) => findAll(root, e => e.tag === 'button' && e.textContent.startsWith(text)),
    detailText: () => q('#detail').textContent,
    open(title) {
      const item = view.items().find(e => findAll(e, x => x.tag === 'strong')[0].textContent === title);
      assert.ok(item, 'list item present: ' + title);
      item.click();
    },
    stateButton: label => findAll(q('#state-filters'), e => e.tag === 'button' && e.textContent.startsWith(label))[0],
  };
  return view;
}

// --- sample payload --------------------------------------------------------
const node = (over) => ({
  id: over.id, path: over.path, title: over.title, type: over.type, status: '', areas: ['areas/a'],
  updated: '2026-11-01', body: '', tags: [], stale: false, kind: '', recheck: '', recheckedBy: '',
  recheckedOn: '', decision: '', decidedBy: '', decidedOn: '', state: '', gap: '', layer: '', ...over,
});
const gap = (id, title, over) => node({ id, title, type: 'gap', layer: 'gap', path: `gaps/${id}.md`, kind: 'product-gap', recheck: 'not-checked', decision: 'open', ...over });
const sample = {
  title: 'Sample vault',
  nodes: [
    node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md' }),
    node({ id: 'run1', title: 'Run one', type: 'run', layer: 'nav', status: 'current', path: 'runs/run1.md' }),
    node({ id: 'areas/a', title: 'Area A', type: 'area', layer: 'spec', status: 'current', path: 'areas/a.md', areas: ['areas/a'] }),
    node({ id: 'note-a', title: 'Note A', type: 'note', layer: 'spec', status: 'current', path: 'notes/a.md' }),
    gap('g-recheck', 'Gap recheck', { state: 'needs-recheck', priority: 'P1' }),
    gap('g-decision', 'Gap decision', { state: 'needs-decision', recheck: 'confirmed', recheckedBy: 'agent', recheckedOn: '2026-11-05', kind: 'verification-gap' }),
    gap('g-accepted', 'Gap accepted', { state: 'accepted', decision: 'accepted', decidedBy: 'Ann', decidedOn: '2026-11-10', recheck: 'confirmed', recheckedBy: 'Bob', recheckedOn: '2026-11-08' }),
    gap('g-deferred', 'Gap deferred', { state: 'deferred', decision: 'deferred', decidedBy: 'Ann', decidedOn: '2026-11-11', kind: 'product-plan' }),
    gap('g-rejected', 'Gap rejected', { state: 'rejected', decision: 'rejected', decidedBy: 'Ann', decidedOn: '2026-11-12' }),
    gap('g-done', 'Gap done', { state: 'done', decision: 'done', kind: 'conflict' }),
    gap('g-dup', 'Gap duplicate', { state: 'duplicate', decision: 'duplicate' }),
    // state missing: must be derived from decision/recheck
    gap('g-derive', 'Gap derived', { state: '', recheck: 'not-reproduced', recheckedBy: 'Cy', recheckedOn: '2026-11-09' }),
    // recheck outdated (explicit value, state derived) and a rechecked gap whose sources changed (flag only)
    gap('g-outdated', 'Gap outdated', { state: '', recheck: 'outdated', recheckedBy: 'Dee', recheckedOn: '2026-10-01', recheckOutdated: true }),
    gap('g-outflag', 'Gap flagged', { state: 'needs-decision', recheck: 'confirmed', recheckedBy: 'Eve', recheckedOn: '2026-10-02', recheckOutdated: true }),
    gap('g-outnoflag', 'Gap outdated no flag', { state: '', recheck: 'outdated', recheckedBy: 'Fay', recheckedOn: '2026-10-03' }),
    // legacy gap: none of the new fields, status still set
    { id: 'g-legacy', path: 'gaps/legacy.md', title: 'Legacy gap', type: 'gap', status: 'unverified', areas: ['areas/a'], body: 'old', tags: ['product-gap'] },
    node({ id: 'plan-1', title: 'Plan A', type: 'plan', layer: 'gap', status: 'planned', path: 'plans/p.md', gap: 'g-accepted' }),
  ],
  edges: [
    { source: 'areas/a', target: 'note-a' },
    { source: 'g-recheck', target: 'note-a' },
    { source: 'g-accepted', target: 'note-a' },
    { source: 'g-legacy', target: 'note-a' },
    { source: 'g-accepted', target: 'plan-1' },
    { source: 'plan-1', target: 'note-a' },
    { source: 'idx', target: 'g-recheck' },
    { source: 'g-outflag', target: 'note-a' },
  ],
};

// --- Spec mode (default) ---------------------------------------------------
{
  const v = load(sample);
  assert.equal(v.mode(), 'spec');
  assert.equal(v.q('#mode-spec').attrs['aria-pressed'], 'true');
  assert.equal(v.q('#mode-gaps').attrs['aria-pressed'], 'false');
  assert.deepEqual(v.itemTitles().sort(), ['Area A', 'Index page', 'Note A', 'Run one']);
  assert.deepEqual(v.graphLabels().sort(), ['Area A', 'Index page', 'Note A', 'Run one']);
  assert.equal(v.q('#panel-gaps').hidden, true);
  assert.equal(v.q('#panel-spec').hidden, false);
  assert.equal(v.q('#mode-wait').textContent, '7 waiting', 'recheck(4: explicit + legacy + 2 outdated) + decision(3)');

  // spec note: compact "Gaps about this" with state badges, plans excluded
  v.open('Note A');
  const text = v.detailText();
  assert.ok(text.includes('Gaps about this (4)'), text);
  const block = findAll(v.q('#detail'), e => cls(e).includes('link-block'))[0];
  const rows = findAll(block, e => e.tag === 'li').map(e => e.textContent);
  assert.deepEqual(rows, ['Gap recheckNeeds recheck', 'Legacy gapNeeds recheck', 'Gap flaggedNeeds decisionRecheck outdated', 'Gap acceptedAccepted']);

  // clicking one switches to Gaps mode with that gap open
  v.buttons(block, 'Gap accepted')[0].click();
  assert.equal(v.mode(), 'gap');
  assert.equal(v.q('#mode-gaps').attrs['aria-pressed'], 'true');
  assert.ok(v.detailText().includes('Gap accepted'));
  assert.ok(findAll(v.q('#detail'), e => e.tag === 'h1')[0].textContent === 'Gap accepted');
  const facts = findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0];
  assert.ok(cls(facts).includes('st-accepted'));
  assert.ok(facts.textContent.includes('Accepted'), 'state badge text, not color only');
  assert.ok(facts.textContent.includes('Decision') && facts.textContent.includes('by Ann on 2026-11-10'));
  assert.ok(facts.textContent.includes('Recheck') && facts.textContent.includes('Confirmed by Bob on 2026-11-08'));
  const links = findAll(v.q('#detail'), e => cls(e).includes('link-block')).map(e => e.textContent);
  assert.ok(links.some(t => t.startsWith('Refers to') && t.includes('Note A')), links.join('|'));
  assert.ok(links.some(t => t.startsWith('Plan') && t.includes('Plan A')), links.join('|'));
  // plan page links back to its gap
  v.buttons(findAll(v.q('#detail'), e => cls(e).includes('link-block')).find(b => b.textContent.startsWith('Plan')), 'Plan A')[0].click();
  assert.equal(v.mode(), 'gap');
  assert.ok(v.detailText().includes('Plan for gap') && v.detailText().includes('Gap accepted'));
}

// --- Gaps mode -------------------------------------------------------------
{
  const v = load(sample);
  v.q('#mode-gaps').click();
  assert.equal(v.mode(), 'gap');
  assert.equal(v.q('#panel-gaps').hidden, false);
  assert.equal(v.q('#panel-spec').hidden, true);
  // queue: gaps only, ordered needs-recheck, needs-decision, ...
  assert.deepEqual(v.itemTitles(), [
    'Gap outdated', 'Gap outdated no flag', 'Gap recheck', 'Legacy gap', 'Gap decision', 'Gap derived', 'Gap flagged', 'Gap accepted', 'Gap deferred', 'Gap rejected', 'Gap done', 'Gap duplicate',
  ]);
  // index/run pages stay reachable
  assert.deepEqual(v.navTitles().sort(), ['Index page', 'Run one']);
  assert.equal(v.q('#nav-block').hidden, false);
  // counts per state, derived when `state` is missing (legacy and g-derive)
  const counts = Object.fromEntries(['All', 'Needs recheck', 'Needs decision', 'Accepted', 'Deferred', 'Rejected', 'Done', 'Duplicate']
    .map(l => { const b = v.stateButton(l); return [l, b.textContent.slice(l.length)]; }));
  assert.deepEqual(counts, { All: '12', 'Needs recheck': '4', 'Needs decision': '3', Accepted: '1', Deferred: '1', Rejected: '1', Done: '1', Duplicate: '1' });
  // row facts and badge text
  const decisionRow = v.items().find(e => e.textContent.includes('Gap decision'));
  assert.ok(decisionRow.textContent.includes('Verification gap') && decisionRow.textContent.includes('Needs decision'));
  assert.ok(decisionRow.textContent.includes('Rechecked by agent on 2026-11-05'));
  const acceptedRow = v.items().find(e => e.textContent.includes('Gap accepted'));
  assert.ok(acceptedRow.textContent.includes('Decided by Ann on 2026-11-10'));
  assert.ok(v.items().find(e => e.textContent.includes('Gap recheck')).textContent.includes('Priority P1'));

  // recheck-outdated badge: queue row (text, not color), only where it applies
  const badgeText = t => t.includes('Recheck outdated');
  const rowFor = title => v.items().find(e => findAll(e, x => x.tag === 'strong')[0].textContent === title);
  assert.ok(badgeText(rowFor('Gap outdated').textContent), 'explicit outdated, flag set');
  assert.ok(badgeText(rowFor('Gap outdated no flag').textContent), 'flag absent but recheck === outdated');
  assert.ok(badgeText(rowFor('Gap flagged').textContent), 'confirmed but sources changed (flag only)');
  assert.ok(!badgeText(rowFor('Gap recheck').textContent) && !badgeText(rowFor('Gap decision').textContent));
  assert.ok(rowFor('Gap flagged').textContent.includes('Needs decision'), 'state unchanged by flag');
  assert.ok(rowFor('Gap outdated').textContent.includes('Needs recheck'), 'outdated derives needs-recheck');
  // graph aria-label
  assert.ok(v.graphLabels().includes('Gap flagged (Needs decision), recheck outdated'));
  assert.ok(v.graphLabels().includes('Gap outdated no flag (Needs recheck), recheck outdated'));
  assert.ok(v.graphLabels().includes('Gap recheck (Needs recheck)'));
  // facts block: recheck line shows who/when only, plus the badge
  v.open('Gap outdated');
  let fb = findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent;
  assert.ok(fb.includes('Outdated (last by Dee on 2026-10-01)'), fb);
  assert.ok(badgeText(fb));
  v.open('Gap flagged');
  fb = findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent;
  assert.ok(fb.includes('Confirmed by Eve on 2026-10-02') && badgeText(fb), fb);
  v.open('Gap recheck');
  assert.ok(!badgeText(findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent));

  // state filter + pressed state
  v.stateButton('Needs decision').click();
  assert.deepEqual(v.itemTitles(), ['Gap decision', 'Gap derived', 'Gap flagged']);
  assert.equal(v.stateButton('Needs decision').attrs['aria-pressed'], 'true');
  assert.equal(v.stateButton('All').attrs['aria-pressed'], 'false');
  v.stateButton('All').click();
  // kind filter
  v.q('#kind').value = 'product-plan';
  v.q('#kind').fire('change');
  assert.deepEqual(v.itemTitles(), ['Gap deferred']);
  v.q('#kind').value = '';
  v.q('#kind').fire('change');
  // area filter
  v.q('#area').value = 'areas/other';
  v.q('#area').fire('change');
  assert.deepEqual(v.itemTitles(), []);
  assert.ok(v.q('#list').textContent.includes('No results'));
  v.q('#area').value = '';
  v.q('#area').fire('change');

  // graph: gaps + plan + linked spec context; context is visually distinct; no nav pages
  const labels = v.graphLabels();
  assert.ok(labels.includes('Gap recheck (Needs recheck)') && labels.includes('Plan A (Plan)') && labels.includes('Note A'));
  assert.ok(!labels.includes('Index page') && !labels.includes('Run one'));
  assert.ok(cls(v.graphNode('Note A')).includes('context'));
  assert.ok(!cls(v.graphNode('Gap recheck (Needs recheck)')).includes('context'));
  assert.ok(cls(v.graphNode('Gap decision (Needs decision)')).includes('st-needs-decision'));
  assert.ok(findAll(v.graphNode('Plan A (Plan)'), e => e.tag === 'rect').length === 1, 'plans are squares');

  // back to Spec: gap nodes are not drawn
  v.q('#mode-spec').click();
  assert.equal(v.mode(), 'spec');
  assert.ok(!v.graphLabels().some(l => l.startsWith('Gap ') || l.startsWith('Plan')));
  assert.equal(v.q('#nav-block').hidden, true);
}

// --- jumping to a gap clears hiding filters --------------------------------
{
  const v = load(sample);
  v.q('#mode-gaps').click();
  v.stateButton('Done').click();
  v.q('#mode-spec').click();
  v.open('Note A');
  const block = findAll(v.q('#detail'), e => cls(e).includes('link-block'))[0];
  v.buttons(block, 'Gap recheck')[0].click();
  assert.equal(v.mode(), 'gap');
  assert.ok(v.itemTitles().includes('Gap recheck'), 'state filter was reset so the opened gap is listed');
  assert.equal(v.stateButton('All').attrs['aria-pressed'], 'true');
}

// --- legacy payload: none of the new fields -------------------------------
{
  const legacy = {
    title: 'Old vault',
    nodes: [
      { id: 'idx', path: '00-index.md', title: 'Index', type: 'index', status: 'current', areas: [], body: '', tags: [], stale: false },
      { id: 'areas/a', path: 'areas/a.md', title: 'Area', type: 'area', status: 'current', areas: ['areas/a'], body: 'x' },
      { id: 'n', path: 'notes/n.md', title: 'Old note', type: 'note', status: 'unverified', areas: ['areas/a'], body: 'text [[gaps/g]]' },
      { id: 'g', path: 'gaps/g.md', title: 'Old gap', type: 'gap', status: 'conflict', areas: ['areas/a'], body: 'gap body', tags: ['conflict'] },
      { id: 'weird', title: 'No path or areas', type: 'mystery' },
    ],
    edges: [{ source: 'n', target: 'g' }],
  };
  const v = load(legacy);
  assert.equal(v.mode(), 'spec');
  assert.deepEqual(v.itemTitles().sort(), ['Area', 'Index', 'No path or areas', 'Old note']);
  v.open('Old note'); // legacy spec -> gap edge still yields "Gaps about this"
  assert.ok(v.detailText().includes('Gaps about this (1)'));
  findAll(v.q('#detail'), e => e.tag === 'button' && e.textContent === 'Old gap')[0].click();
  assert.equal(v.mode(), 'gap');
  assert.deepEqual(v.itemTitles(), ['Old gap']);
  assert.ok(v.detailText().includes('Needs recheck'), 'derived state for legacy gap');
  assert.ok(!v.detailText().includes('Recheck outdated'), 'no badge on legacy payloads');
  assert.ok(!v.items().some(e => e.textContent.includes('Recheck outdated')));
  assert.ok(!v.graphLabels().some(l => l.includes('outdated')));
  assert.ok(v.detailText().includes('Conflict'), 'legacy tag note kept');
  // no edges / nodes keys at all
  assert.doesNotThrow(() => load({}));
  assert.doesNotThrow(() => load({ nodes: [], edges: null }));
}

// --- Markdown rendering ----------------------------------------------------
function article(body) {
  const v = load({ nodes: [
    node({ id: 'n', title: 'N', type: 'note', layer: 'spec', path: 'notes/n.md', body }),
    node({ id: 'l', title: 'Legacy', type: 'note', layer: 'spec', path: 'notes/legacy.md' }),
  ], edges: [] });
  v.open('N');
  return { v, art: findAll(v.q('#detail'), e => cls(e) === 'article')[0] };
}
const pres = art => findAll(art, e => e.tag === 'pre').map(e => e.textContent);

assert.deepEqual(pres(article('````md\n```js\ninner\n```\n````\nafter').art), ['```js\ninner\n```'], 'longer fence wraps shorter one');
assert.deepEqual(pres(article('~~~\ntilde ```\nx\n~~~\n').art), ['tilde ```\nx'], 'tilde fence');
assert.deepEqual(pres(article('```\nx\n~~~\ny\n```').art), ['x\n~~~\ny'], 'other character does not close');
assert.deepEqual(pres(article('````\na\n```\nb\n````').art), ['a\n```\nb'], 'shorter closer does not close');
assert.deepEqual(pres(article('```\nx\n```js\ny\n```').art), ['x\n```js\ny'], 'closer with info string does not close');
assert.deepEqual(pres(article('``` a`b\ntext').art), [], 'backtick in info string is not a fence');
assert.deepEqual(pres(article('~~~ a`b\ntext\n~~~').art), ['text'], 'backtick is fine in a tilde info string');
assert.deepEqual(pres(article('```\nunclosed').art), ['unclosed'], 'unclosed fence still rendered');
assert.deepEqual(pres(article('```js\none\n```\n\ntext\n\n```\ntwo\n```').art), ['one', 'two']);
{
  // wikilink with escaped pipe inside a table row
  const { v, art } = article('| Link | Other |\n| --- | --- |\n| [[notes/legacy\\|Alias]] | [[notes/legacy|Plain]] |');
  const wiki = findAll(art, e => e.tag === 'button' && cls(e) === 'wiki');
  assert.deepEqual(wiki.map(e => e.textContent), ['Alias', 'Plain']);
  wiki[0].click();
  assert.equal(findAll(v.q('#detail'), e => e.tag === 'h1')[0].textContent, 'Legacy', 'escaped pipe resolves to notes/legacy');
}
{
  // inline formatting and hostile text
  const { art } = article('**[[notes/legacy|label]]** and **[source](https://example.com)** and **`code`**');
  const strongs = findAll(art, e => e.tag === 'strong');
  assert.equal(findAll(strongs[0], e => e.tag === 'button').length, 1);
  const anchor = findAll(strongs[1], e => e.tag === 'a')[0];
  assert.equal(anchor.href, 'https://example.com/');
  assert.equal(findAll(strongs[2], e => e.tag === 'code').length, 1);
  const hostile = article('<img src=x onerror=alert(1)> [bad](javascript:alert) [ok](mailto:a@b.c)').art;
  assert.equal(findAll(hostile, e => e.tag === 'img').length, 0);
  assert.deepEqual(findAll(hostile, e => e.tag === 'a').map(e => e.href), ['mailto:a@b.c']);
  assert.ok(hostile.textContent.includes('<img src=x onerror=alert(1)>'));
}

console.log('PASS: viewer markdown, modes, state derivation, legacy payloads');
