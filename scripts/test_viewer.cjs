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

// The viewer opens in Read; most checks below are about the Map and Gaps views, so load() switches to Map unless told otherwise.
function load(payload, startMode = 'spec') {
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
    outline: () => findAll(q('#outline'), e => e.tag === 'button').map(e => e.textContent),
    pageText: () => q('#page').textContent,
    pageButton: text => findAll(q('#page'), e => e.tag === 'button' && e.textContent === text)[0],
    folds: () => findAll(q('#page'), e => e.tag === 'summary').map(e => e.textContent),
  };
  assert.equal(body.dataset.mode, 'read', 'the viewer opens in Read');
  if (startMode !== 'read') q('#mode-spec').click();
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
  // the map shows spec pages only: index, coverage and run pages are listed but not drawn
  assert.deepEqual(v.graphLabels().sort(), ['Area A', 'Note A']);
  // one frame per area; membership is the frame, not a line
  assert.equal(findAll(v.q('#graph'), e => cls(e) === 'cluster').length, 1);
  assert.equal(findAll(v.q('#graph'), e => e.tag === 'line').length, 0);
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
  assert.ok(facts.textContent.includes('Recheck') && facts.textContent.includes('Confirmed (still holds) by Bob on 2026-11-08'));
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
  assert.ok(fb.includes('Confirmed (still holds) by Eve on 2026-10-02') && badgeText(fb), fb);
  v.open('Gap recheck');
  assert.ok(!badgeText(findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent));

  // recheck wording is the same for every kind, incl. a product-plan gap
  v.open('Gap deferred');
  assert.ok(findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent.includes('Product plan'));
  v.open('Gap derived');
  assert.ok(findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent.includes('Not reproduced (no longer holds) by Cy on 2026-11-09'));
  // explanation for the waiting states: chip titles + hint line for the selected chip
  assert.ok(v.stateButton('Needs recheck').attrs.title === undefined && v.stateButton('Needs recheck').title.includes('confirm'));
  assert.ok(v.stateButton('Needs decision').title.includes('accept, reject or defer'));
  assert.equal(v.stateButton('Accepted').title, undefined);
  assert.equal(v.q('#state-hint').hidden, true);
  v.stateButton('Needs decision').click();
  assert.equal(v.q('#state-hint').hidden, false);
  assert.ok(v.q('#state-hint').textContent.includes('waiting for a person'));
  v.stateButton('Needs recheck').click();
  assert.ok(v.q('#state-hint').textContent.includes('current code'));
  v.stateButton('All').click();
  assert.equal(v.q('#state-hint').hidden, true);

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

// --- recheck wording on a product-plan gap --------------------------------
{
  const v = load({ nodes: [
    gap('pp', 'Proposal', { kind: 'product-plan', recheck: 'confirmed', recheckedBy: 'Ann', recheckedOn: '2026-11-14' }),
    gap('kg', 'Research', { kind: 'knowledge-gap', recheck: 'not-reproduced', recheckedBy: 'agent', recheckedOn: '2026-11-14' }),
    gap('nc', 'Unchecked', { kind: 'product-plan' }),
  ], edges: [] });
  v.q('#mode-gaps').click();
  const facts = t => { v.open(t); return findAll(v.q('#detail'), e => cls(e).includes('gap-facts'))[0].textContent; };
  assert.ok(facts('Proposal').includes('Confirmed (still holds) by Ann on 2026-11-14'));
  assert.ok(facts('Research').includes('Not reproduced (no longer holds) by agent on 2026-11-14'));
  assert.ok(facts('Unchecked').includes('Not checked'));
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

// --- area clusters ---------------------------------------------------------
{
  const spec = (id, title, type, areas) => node({ id, title, type, layer: 'spec', status: 'current', path: `${id}.md`, areas });
  const v = load({
    title: 'Clusters',
    nodes: [
      node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md', areas: [] }),
      node({ id: 'run1', title: 'Run one', type: 'run', layer: 'nav', status: 'current', path: 'runs/run1.md', areas: [] }),
      spec('a', 'Area A', 'area', []), spec('b', 'Area B', 'area', []),
      spec('a1', 'A one', 'note', ['a']), spec('a2', 'A two', 'note', ['a']), spec('b1', 'B one', 'note', ['b', 'a']),
      gap('g-b', 'Gap in B', { state: 'needs-recheck', areas: ['b'] }),
    ],
    edges: [
      { source: 'idx', target: 'a' }, { source: 'idx', target: 'b' }, { source: 'run1', target: 'a1' },
      { source: 'a', target: 'a1' }, { source: 'a', target: 'a2' }, { source: 'b', target: 'b1' },
      { source: 'a', target: 'b1' },   // second area of b1: a real cross-area relation
      { source: 'a1', target: 'a2' },  // inside one area
      { source: 'a2', target: 'b1' },  // across areas
      { source: 'g-b', target: 'b1' },
    ],
  });
  const svg = v.q('#graph');
  const frames = findAll(svg, e => cls(e) === 'cluster');
  const xy = label => v.graphNode(label).attrs.transform.match(/-?[\d.]+/g).map(Number);
  const inside = (label, f) => {
    const [x, y] = xy(label), fx = +f.attrs.x, fy = +f.attrs.y;
    return x > fx && x < fx + +f.attrs.width && y > fy && y < fy + +f.attrs.height;
  };
  assert.deepEqual(v.graphLabels().sort(), ['A one', 'A two', 'Area A', 'Area B', 'B one']);
  assert.equal(frames.length, 2);
  const frameOf = label => frames.filter(f => inside(label, f));
  for (const label of ['Area A', 'A one', 'A two', 'Area B', 'B one']) assert.equal(frameOf(label).length, 1, label + ' sits in exactly one frame');
  assert.equal(frameOf('A one')[0], frameOf('Area A')[0]);
  assert.equal(frameOf('A two')[0], frameOf('Area A')[0]);
  assert.equal(frameOf('B one')[0], frameOf('Area B')[0]);
  assert.notEqual(frameOf('Area A')[0], frameOf('Area B')[0]);
  // frames do not overlap
  const [f1, f2] = frames.map(f => ({ x: +f.attrs.x, y: +f.attrs.y, w: +f.attrs.width, h: +f.attrs.height }));
  assert.ok(f1.x + f1.w <= f2.x || f2.x + f2.w <= f1.x || f1.y + f1.h <= f2.y || f2.y + f2.h <= f1.y);
  // lines: a1-a2 (plain), a2-b1 and a-b1 (cross); the three membership edges and nav edges are not drawn
  const lines = findAll(svg, e => e.tag === 'line');
  assert.equal(lines.length, 3);
  assert.equal(lines.filter(l => cls(l) === 'cross').length, 2);
  // Gaps mode: the gap's area page is not shown, so its frame gets a plain label
  v.q('#mode-gaps').click();
  assert.deepEqual(v.graphLabels().sort(), ['B one', 'Gap in B (Needs recheck)']);
  const labels = findAll(svg, e => cls(e) === 'cluster-label');
  assert.deepEqual(labels.map(e => e.textContent), ['Area B']);
  assert.equal(findAll(svg, e => cls(e) === 'cluster').length, 1);
}

// --- Read mode: the spec as a document ---------------------------------------
{
  const spec = (id, title, type, areas, over) => node({ id, title, type, layer: 'spec', status: 'current', path: `${type}s/${id}.md`, areas, ...over });
  const v = load({
    title: 'Parcel Desk',
    nodes: [
      node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md', areas: [] }),
      node({ id: 'run1', title: 'Run one', type: 'run', layer: 'nav', status: 'current', path: 'runs/run1.md', areas: [] }),
      spec('pickups', 'Pickups', 'area', [], { summary: 'How a pickup is cancelled.', body: '# Pickups\n\nArea map text.' }),
      spec('access', 'Access', 'area', [], { summary: 'Who may change a pickup.' }),
      spec('cancel', 'Cancelling a pickup', 'note', ['pickups'], {
        summary: 'A customer can cancel a pickup until it is packed.', sources: ['src/pickups.py'], updated: '2026-11-14',
        body: '# Cancelling a pickup\n\n`cancel_pickup` checks [[notes/owner|the owner]] first.',
      }),
      spec('responses', 'Responses', 'note', ['pickups'], { body: '# Responses\n\nErrors become status codes.' }),
      spec('owner', 'Owner check', 'note', ['access'], { summary: 'Only the owner may change a pickup.' }),
      spec('old', 'Old rule', 'note', ['pickups'], { status: 'superseded' }),
      gap('g-open', 'Packed pickups', { state: 'needs-decision', areas: ['pickups'] }),
      gap('g-done', 'Closed question', { state: 'done', decision: 'done', areas: ['pickups'] }),
    ],
    edges: [
      { source: 'pickups', target: 'cancel' }, { source: 'pickups', target: 'responses' }, { source: 'access', target: 'owner' },
      { source: 'cancel', target: 'owner' }, { source: 'g-open', target: 'cancel' }, { source: 'g-done', target: 'cancel' },
      { source: 'run1', target: 'cancel' },
    ],
  }, 'read');
  // chrome: Read is on, the map workspace is hidden
  assert.equal(v.mode(), 'read');
  assert.equal(v.q('#mode-read').attrs['aria-pressed'], 'true');
  assert.equal(v.q('#reading').hidden, false);
  assert.equal(v.q('.workspace').hidden, true);
  // outline: project, then each area with its features; no index, runs, gaps or superseded notes
  assert.deepEqual(v.outline(), ['Parcel Desk', 'Access', 'Owner check', 'Pickups', 'Cancelling a pickup', 'Responses']);
  // overview: areas with summaries and features with their plain-language line; gaps only as a quiet count
  const home = v.pageText();
  for (const text of ['Parcel Desk', 'How a pickup is cancelled.', 'A customer can cancel a pickup until it is packed.', '1 open question'])
    assert.ok(home.includes(text), 'overview shows: ' + text);
  for (const text of ['cancel_pickup', 'src/pickups.py', 'Old rule', 'Run one', 'Index page', 'Packed pickups', 'current'])
    assert.ok(!home.includes(text), 'overview hides: ' + text);
  assert.deepEqual(v.folds(), []);
  // a feature with a summary: the summary leads, code detail and questions are folded, no properties in the open text
  v.pageButton('Cancelling a pickup').click();
  assert.equal(v.mode(), 'read');
  assert.deepEqual(v.folds(), ['How it works in the code', 'Open questions and planned changes (1)', 'Technical details']);
  const page = v.q('#page');
  const outside = findAll(page, e => e.tag === 'p' && cls(e) === 'lead').map(e => e.textContent);
  assert.deepEqual(outside, ['A customer can cancel a pickup until it is packed.']);
  const folded = findAll(page, e => e.tag === 'details');
  assert.ok(folded[0].textContent.includes('cancel_pickup'));
  assert.equal(findAll(folded[0], e => e.tag === 'h1').length, 0, 'the duplicate title heading is dropped');
  assert.ok(folded[1].textContent.includes('Packed pickups') && !folded[1].textContent.includes('Closed question'));
  assert.ok(folded[2].textContent.includes('src/pickups.py') && folded[2].textContent.includes('2026-11-14'));
  assert.equal(findAll(page, e => e.tag === 'h1').map(e => e.textContent).join('|'), 'Cancelling a pickup');
  assert.ok(findAll(page, e => cls(e) === 'crumbs')[0].textContent.includes('Pickups'));
  // related pages are named, the own area and run pages are not
  assert.deepEqual(findAll(page, e => cls(e) === 'chip').map(e => e.textContent), ['Owner check']);
  // a link inside the text stays in Read
  findAll(folded[0], e => cls(e) === 'wiki')[0].click();
  assert.equal(v.mode(), 'read');
  assert.equal(findAll(v.q('#page'), e => e.tag === 'h1')[0].textContent, 'Owner check');
  // a feature without a summary shows its text directly
  v.pageButton('Parcel Desk').click();
  v.pageButton('Responses').click();
  assert.deepEqual(v.folds(), ['Technical details']);
  assert.ok(v.pageText().includes('Errors become status codes.'));
  // an area page lists its features and folds its own text
  findAll(v.q('#outline'), e => e.tag === 'button' && e.textContent === 'Pickups')[0].click();
  assert.deepEqual(v.folds(), ['More about this area', 'Technical details']);
  assert.ok(v.pageButton('Cancelling a pickup') && v.pageButton('Responses') && !v.pageButton('Old rule'));
  // search narrows the outline
  v.q('#read-search').value = 'owner';
  v.q('#read-search').fire('input');
  assert.deepEqual(v.outline(), ['Parcel Desk', 'Access', 'Owner check', 'Pickups', 'Cancelling a pickup']);
  v.q('#read-search').value = '';
  v.q('#read-search').fire('input');
  // opening a question leaves Read for Gaps; Read comes back to the same kind of page
  v.pageButton('Cancelling a pickup').click();
  findAll(v.q('#page'), e => e.tag === 'button' && e.textContent === 'Packed pickups')[0].click();
  assert.equal(v.mode(), 'gap');
  assert.equal(v.q('#reading').hidden, true);
  assert.equal(v.q('.workspace').hidden, false);
  // Graph and page share the width: opening an item shows the page, changing the layer goes back to the graph
  const ws = v.q('.workspace');
  assert.equal(ws.dataset.view, 'reader');
  v.q('#mode-spec').click();
  assert.equal(ws.dataset.view, 'map');
  v.open('Cancelling a pickup');
  assert.equal(ws.dataset.view, 'reader');
  v.q('#mode-gaps').click();
  assert.equal(ws.dataset.view, 'map');
  // Map keeps the page that was being read; Read returns to it
  v.q('#mode-read').click();
  v.pageButton('Parcel Desk').click();
  v.pageButton('Owner check').click();
  v.q('#mode-spec').click();
  assert.equal(v.mode(), 'spec');
  assert.ok(v.detailText().includes('Owner check'));
  v.q('#mode-read').click();
  assert.equal(findAll(v.q('#page'), e => e.tag === 'h1')[0].textContent, 'Owner check');
}

console.log('PASS: viewer markdown, modes, state derivation, legacy payloads, area clusters, read mode');
