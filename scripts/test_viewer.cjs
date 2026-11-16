// DOM-stub checks for the viewer; run with Node, no dependencies.
// The viewer's real script runs against a tiny fake DOM, so these checks
// exercise the shipped code (navigation, pages, gaps, map, search, copy,
// changes, requests, Markdown), not a copy of it.
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
const has = (e, name) => cls(e).split(' ').includes(name);
const text = e => e.textContent;

function memory() {
  const map = new Map();
  return { map, getItem: k => (map.has(k) ? map.get(k) : null), setItem: (k, v) => { map.set(k, String(v)); } };
}

// Loads the viewer with a payload. `hash` plays the address bar; `storage` plays this browser's localStorage.
function load(payload, { hash, storage = memory() } = {}) {
  const registry = new Map();
  const copied = [];
  const document = {
    baseURI: 'http://127.0.0.1:8757/',
    title: '',
    createElement: tag => new FakeEl(tag),
    createElementNS: (ns, tag) => new FakeEl(tag),
    createTextNode: value => ({ text: String(value) }),
    getElementById: () => ({ textContent: JSON.stringify(payload) }),
    querySelector(sel) {
      if (!registry.has(sel)) registry.set(sel, new FakeEl('div'));
      return registry.get(sel);
    },
    querySelectorAll: () => [],
  };
  const ctx = vm.createContext({
    document, URL, Map, Set,
    localStorage: storage,
    navigator: { clipboard: { writeText: value => { copied.push(value); return { then: ok => ok() }; } } },
    location: hash == null ? undefined : { hash, href: 'http://127.0.0.1:8757/' + hash },
  });
  vm.runInContext(script, ctx);
  const q = sel => document.querySelector(sel);
  const buttons = (root, pred = () => true) => findAll(root, e => e.tag === 'button' && pred(e));
  const v = {
    q, copied, storage, document,
    page: () => q('#view'),
    h1: () => (findAll(q('#view'), e => e.tag === 'h1')[0] || {}).textContent,
    nav: () => buttons(q('#nav-links')).map(b => b.children.map(text)),
    go: label => buttons(q('#nav-links'), b => b.children[0].textContent === label)[0].click(),
    tree: () => buttons(q('#tree'), b => has(b, 'tree-row')).map(b => b.children[0].textContent),
    treeRow: title => buttons(q('#tree'), b => has(b, 'tree-row') && b.children[0].textContent === title)[0],
    twist: title => buttons(q('#tree'), b => has(b, 'twist') && b.attrs['aria-label'].endsWith(' ' + title))[0],
    crumbs: () => q('#crumbs').children.map(text),
    btn: (root, label) => buttons(root, b => b.textContent === label)[0],
    pill: (root, label) => buttons(root, b => has(b, 'pill') && b.children[0].text === label)[0],
    select: label => findAll(q('#view'), e => e.tag === 'select' && e.attrs['aria-label'] === label)[0],
    rows: () => findAll(q('#view'), e => has(e, 'row')),
    rowTitles: () => findAll(q('#view'), e => has(e, 'row')).map(r => findAll(r, e => has(e, 'grow'))[0].children[0].textContent),
    folds: () => findAll(q('#view'), e => e.tag === 'summary').map(text),
    chips: () => findAll(q('#view'), e => has(e, 'chip')).map(text),
    article: () => findAll(q('#view'), e => cls(e) === 'article')[0],
    search(query, kind = 'open') {
      if (kind === 'open') q('#open-search').click();
      q('#palette-input').value = query;
      q('#palette-input').fire('input');
      return v.results();
    },
    results: () => findAll(q('#palette-results'), e => cls(e) === 'result'),
    resultNames: () => v.results().map(r => findAll(r, e => has(e, 'grow'))[0].children[0].textContent),
    groups: () => findAll(q('#palette-results'), e => cls(e) === 'eyebrow').map(text),
    // Opens any page by its title through search, the way a reader would.
    open(title) {
      const hit = v.search(title).find(r => findAll(r, e => has(e, 'grow'))[0].children[0].textContent === title);
      assert.ok(hit, 'search finds: ' + title);
      hit.click();
      assert.equal(v.h1(), title);
    },
    graphLabels: () => findAll(q('#graph'), e => e.attrs.role === 'button').map(e => e.attrs['aria-label']),
    graphNode: label => findAll(q('#graph'), e => e.attrs['aria-label'] === label)[0],
  };
  return v;
}

// --- sample payloads --------------------------------------------------------
const node = (over) => ({
  id: over.id, path: over.path, title: over.title, type: over.type, status: '', areas: ['areas/a'],
  updated: '2026-11-01', body: '', tags: [], stale: false, kind: '', recheck: '', recheckedBy: '',
  recheckedOn: '', decision: '', decidedBy: '', decidedOn: '', state: '', gap: '', layer: '', ...over,
});
const gap = (id, title, over) => node({ id, title, type: 'gap', layer: 'gap', path: `gaps/${id}.md`, kind: 'product-gap', recheck: 'not-checked', decision: 'open', ...over });
const spec = (id, title, type, areas, over) => node({ id, title, type, layer: 'spec', status: 'current', path: `${type}s/${id}.md`, areas, ...over });

const parcel = () => ({
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
    gap('g-open', 'Packed pickups', { state: 'needs-decision', areas: ['pickups'], priority: 'P1', body: '# Packed pickups\n\n## Current behavior\n\nRefused.' }),
    gap('g-done', 'Closed question', { state: 'done', decision: 'done', areas: ['pickups'] }),
  ],
  edges: [
    { source: 'pickups', target: 'cancel' }, { source: 'pickups', target: 'responses' }, { source: 'access', target: 'owner' },
    { source: 'cancel', target: 'owner' }, { source: 'g-open', target: 'cancel' }, { source: 'g-done', target: 'cancel' },
    { source: 'run1', target: 'cancel' },
  ],
});

// --- overview, tree, pages and knowing where you are --------------------------
{
  const v = load(parcel());
  assert.equal(v.q('#project-title').textContent, 'Parcel Desk');
  assert.equal(v.q('#header-note').textContent, 'Spec');
  assert.deepEqual(v.nav(), [['Overview', ''], ['Recent changes', ''], ['Gaps', '1 waiting'], ['Map', ''], ['Requests', '']]);
  // the tree lists areas; an area opens to its features, without index, runs, gaps or superseded notes
  assert.deepEqual(v.tree(), ['Access', 'Pickups']);
  v.twist('Pickups').click();
  assert.deepEqual(v.tree(), ['Access', 'Pickups', 'Cancelling a pickup', 'Responses']);
  assert.equal(v.twist('Pickups').attrs['aria-expanded'], 'true');
  v.twist('Pickups').click();
  assert.deepEqual(v.tree(), ['Access', 'Pickups']);
  // overview: areas with summaries and features with their plain-language line; gaps only as a quiet count
  const home = v.page().textContent;
  for (const t of ['Parcel Desk', 'How a pickup is cancelled.', 'A customer can cancel a pickup until it is packed.', '1 open question'])
    assert.ok(home.includes(t), 'overview shows: ' + t);
  for (const t of ['cancel_pickup', 'src/pickups.py', 'Old rule', 'Run one', 'Index page', 'Packed pickups'])
    assert.ok(!home.includes(t), 'overview hides: ' + t);
  assert.deepEqual(v.crumbs(), ['Parcel Desk']);
  assert.equal(v.q('#back').disabled, true);
  assert.equal(v.q('#copy-ai').hidden, true, 'nothing to copy on the overview');
  assert.equal(v.q('#copy-link').hidden, true, 'no address to copy without a window');

  // a feature page: summary first, code and sources folded, where you are shown three ways
  v.btn(v.page(), 'Cancelling a pickup').click();
  assert.equal(v.h1(), 'Cancelling a pickup');
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Pickups', '/', 'Cancelling a pickup']);
  assert.deepEqual(v.tree(), ['Access', 'Pickups', 'Cancelling a pickup', 'Responses'], 'the tree opens to the page');
  assert.equal(v.treeRow('Cancelling a pickup').attrs['aria-current'], 'page');
  assert.equal(v.treeRow('Cancelling a pickup').textContent, 'Cancelling a pickup1 open');
  assert.deepEqual(findAll(v.page(), e => cls(e) === 'lead').map(text), ['A customer can cancel a pickup until it is packed.']);
  assert.deepEqual(v.folds(), ['How it works in the code', 'Source files (1)']);
  assert.deepEqual(v.chips(), ['Owner check'], 'related pages, not the own area or a run');
  assert.deepEqual(v.rowTitles(), ['Packed pickups'], 'open questions only');
  assert.ok(v.page().textContent.includes('notes/cancel.md'));
  assert.equal(findAll(v.page(), e => e.tag === 'h1').length, 1, 'the duplicate title heading is dropped');
  const rail = findAll(v.page(), e => cls(e) === 'rail')[0];
  assert.ok(rail.textContent.includes('You came from the overview. Back returns there.'));
  assert.deepEqual(findAll(rail, e => cls(e) === 'now').map(text), ['Cancelling a pickup']);
  assert.equal(v.q('#copy-ai').hidden, false);
  assert.equal(v.q('#back').disabled, false);
  assert.equal(v.q('#forward').disabled, true);

  // a link in the text moves on; Back and Forward walk the trail
  findAll(v.article(), e => cls(e) === 'wiki')[0].click();
  assert.equal(v.h1(), 'Owner check');
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Access', '/', 'Owner check']);
  assert.ok(findAll(v.page(), e => cls(e) === 'rail')[0].textContent.includes('You came from Cancelling a pickup.'));
  assert.deepEqual(findAll(v.page(), e => cls(e) === 'recent')[0].children.slice(1).map(text), ['Cancelling a pickup']);
  v.q('#back').click();
  assert.equal(v.h1(), 'Cancelling a pickup');
  assert.equal(v.q('#forward').disabled, false);
  v.q('#forward').click();
  assert.equal(v.h1(), 'Owner check');
  v.q('#back').click();
  v.q('#back').click();
  assert.deepEqual(v.crumbs(), ['Parcel Desk']);
  assert.equal(v.q('#back').disabled, true);
  // going somewhere new drops the forward trail
  v.treeRow('Access').click();
  assert.equal(v.q('#forward').disabled, true);
  assert.equal(v.h1(), 'Access');
  assert.ok(v.btn(v.page(), 'Owner check'));

  // a feature without a summary shows its text directly; an area folds its own text
  assert.equal(v.twist('Pickups').attrs['aria-expanded'], 'true', 'an area stays open after you leave it');
  v.treeRow('Responses').click();
  assert.deepEqual(v.folds(), []);
  assert.ok(v.page().textContent.includes('Errors become status codes.'));
  v.treeRow('Pickups').click();
  assert.deepEqual(v.folds(), ['More about this area']);
  assert.ok(v.btn(v.page(), 'Cancelling a pickup') && v.btn(v.page(), 'Responses') && !v.btn(v.page(), 'Old rule'));
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Pickups']);

  // a gap reached from a page
  v.treeRow('Cancelling a pickup').click();
  v.btn(v.page(), 'Packed pickups').click();
  assert.equal(v.h1(), 'Packed pickups');
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Gaps', '/', 'Packed pickups']);
  assert.deepEqual(v.chips(), ['Cancelling a pickup'], 'the spec pages it refers to');
  assert.ok(findAll(v.page(), e => has(e, 'gap-facts'))[0].textContent.includes('Needs decision'));
  assert.ok(v.page().textContent.includes('Refused.'));
  assert.equal(v.document.title, 'Packed pickups · Parcel Desk');
}

// --- the address opens a page directly ---------------------------------------------
{
  const v = load(parcel(), { hash: '#/page/notes/owner' });
  assert.equal(v.h1(), 'Owner check');
  assert.equal(v.q('#copy-link').hidden, false);
  v.q('#copy-link').click();
  assert.deepEqual(v.copied, ['http://127.0.0.1:8757/#/page/notes/owner']);
  assert.equal(v.q('#toast').textContent, 'Link copied');
  assert.equal(load(parcel(), { hash: '#/gaps' }).h1(), 'Gaps');
  assert.equal(load(parcel(), { hash: '#/page/notes/nothing' }).h1(), 'Parcel Desk', 'an unknown page falls back to the overview');
  assert.equal(load(parcel(), { hash: '#/whatever' }).h1(), 'Parcel Desk');
}

// --- gap queue ----------------------------------------------------------------
const queue = {
  title: 'Sample vault',
  nodes: [
    node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md' }),
    node({ id: 'areas/a', title: 'Area A', type: 'area', layer: 'spec', status: 'current', path: 'areas/a.md', areas: ['areas/a'] }),
    node({ id: 'areas/other', title: 'Other area', type: 'area', layer: 'spec', status: 'current', path: 'areas/other.md', areas: ['areas/other'] }),
    node({ id: 'note-a', title: 'Note A', type: 'note', layer: 'spec', status: 'current', path: 'notes/a.md' }),
    gap('g-recheck', 'Gap recheck', { state: 'needs-recheck', priority: 'P1' }),
    gap('g-decision', 'Gap decision', { state: 'needs-decision', recheck: 'confirmed', recheckedBy: 'agent', recheckedOn: '2026-11-05', kind: 'verification-gap' }),
    gap('g-accepted', 'Gap accepted', { state: 'accepted', decision: 'accepted', decidedBy: 'Ann', decidedOn: '2026-11-10', recheck: 'confirmed', recheckedBy: 'Bob', recheckedOn: '2026-11-08' }),
    gap('g-deferred', 'Gap deferred', { state: 'deferred', decision: 'deferred', decidedBy: 'Ann', decidedOn: '2026-11-11', kind: 'product-plan' }),
    gap('g-rejected', 'Gap rejected', { state: 'rejected', decision: 'rejected', decidedBy: 'Ann', decidedOn: '2026-11-12' }),
    gap('g-done', 'Gap done', { state: 'done', decision: 'done', kind: 'conflict' }),
    gap('g-dup', 'Gap duplicate', { state: 'duplicate', decision: 'duplicate' }),
    // state missing: must be derived from decision and recheck
    gap('g-derive', 'Gap derived', { state: '', recheck: 'not-reproduced', recheckedBy: 'Cy', recheckedOn: '2026-11-09' }),
    // recheck outdated (explicit value) and a rechecked gap whose sources changed (flag only)
    gap('g-outdated', 'Gap outdated', { state: '', recheck: 'outdated', recheckedBy: 'Dee', recheckedOn: '2026-10-01', recheckOutdated: true }),
    gap('g-outflag', 'Gap flagged', { state: 'needs-decision', recheck: 'confirmed', recheckedBy: 'Eve', recheckedOn: '2026-10-02', recheckOutdated: true }),
    // legacy gap: none of the new fields, status still set
    { id: 'g-legacy', path: 'gaps/legacy.md', title: 'Legacy gap', type: 'gap', status: 'unverified', areas: ['areas/a'], body: 'old', tags: ['product-gap'] },
    node({ id: 'plan-1', title: 'Plan A', type: 'plan', layer: 'gap', status: 'planned', path: 'plans/p.md', gap: 'g-accepted' }),
  ],
  edges: [
    { source: 'areas/a', target: 'note-a' }, { source: 'g-recheck', target: 'note-a' }, { source: 'g-accepted', target: 'note-a' },
    { source: 'g-legacy', target: 'note-a' }, { source: 'g-accepted', target: 'plan-1' }, { source: 'plan-1', target: 'note-a' },
    { source: 'idx', target: 'g-recheck' }, { source: 'g-outflag', target: 'note-a' },
  ],
};
{
  const v = load(queue);
  assert.deepEqual(v.nav()[2], ['Gaps', '6 waiting'], 'recheck (3, one derived from legacy fields) + decision (3)');
  v.go('Gaps');
  assert.equal(v.h1(), 'Gaps');
  assert.deepEqual(v.crumbs(), ['Sample vault', '/', 'Gaps']);
  const counts = () => findAll(v.page(), e => has(e, 'pill')).map(text);
  assert.deepEqual(counts(), ['All11', 'Needs recheck3', 'Needs decision3', 'Accepted1', 'Deferred1', 'Rejected1', 'Done1', 'Duplicate1']);
  // waiting states come first, each sorted by title
  assert.deepEqual(v.rowTitles().slice(0, 6), ['Gap outdated', 'Gap recheck', 'Legacy gap', 'Gap decision', 'Gap derived', 'Gap flagged']);
  v.pill(v.page(), 'Needs decision').click();
  assert.deepEqual(v.rowTitles(), ['Gap decision', 'Gap derived', 'Gap flagged']);
  assert.ok(v.page().textContent.includes('waiting for a person to accept, reject or defer'));
  const flagged = v.rows().find(r => r.textContent.startsWith('Gap flagged'));
  assert.ok(flagged.textContent.includes('Recheck outdated'));
  assert.ok(flagged.textContent.includes('Rechecked by Eve on 2026-10-02'));
  v.pill(v.page(), 'All').click();
  v.select('Kind').value = 'product-plan';
  v.select('Kind').fire('change');
  assert.deepEqual(v.rowTitles(), ['Gap deferred']);
  assert.deepEqual(counts().slice(0, 2), ['All1', 'Needs recheck0'], 'counts follow the other filters');
  v.select('Kind').value = '';
  v.select('Kind').fire('change');
  v.select('Area').value = 'areas/other';
  v.select('Area').fire('change');
  assert.deepEqual(v.rowTitles(), []);
  assert.ok(v.page().textContent.includes('No gaps match'));
  v.select('Area').value = '';
  v.select('Area').fire('change');

  // a gap page: who rechecked and decided, in words
  v.btn(v.page(), 'Gap derived').click();
  const facts = () => findAll(v.page(), e => has(e, 'gap-facts'))[0].textContent;
  assert.ok(facts().includes('Not reproduced (no longer holds) by Cy on 2026-11-09'));
  assert.ok(facts().includes('Needs decision'));
  v.q('#back').click();
  assert.equal(v.h1(), 'Gaps', 'Back returns to the queue');
  v.btn(v.page(), 'Gap outdated').click();
  assert.ok(facts().includes('Outdated (last by Dee on 2026-10-01)'));
  assert.ok(v.page().textContent.includes('Recheck outdated'));
  v.q('#back').click();
  v.btn(v.page(), 'Legacy gap').click();
  assert.ok(facts().includes('Needs recheck'));
  assert.ok(v.page().textContent.includes('Product gap'), 'the old category tag is still shown');
  // an accepted gap leads to its plan and back
  v.q('#back').click();
  v.btn(v.page(), 'Gap accepted').click();
  assert.ok(facts().includes('Accepted by Ann on 2026-11-10'));
  findAll(v.page(), e => cls(e) === 'wiki' && e.textContent === 'Plan A')[0].click();
  assert.equal(v.h1(), 'Plan A');
  assert.deepEqual(v.crumbs(), ['Sample vault', '/', 'Gaps', '/', 'Gap accepted', '/', 'Plan A']);
  assert.ok(findAll(v.page(), e => cls(e) === 'wiki' && e.textContent === 'Gap accepted')[0]);
}

// --- map: one frame per area -----------------------------------------------------
{
  const v = load({
    title: 'Clusters',
    nodes: [
      node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md', areas: [] }),
      node({ id: 'run1', title: 'Run one', type: 'run', layer: 'nav', status: 'current', path: 'runs/run1.md', areas: [] }),
      spec('a', 'Area A', 'area', []), spec('b', 'Area B', 'area', []),
      spec('a1', 'A one', 'note', ['a']), spec('a2', 'A two', 'note', ['a']), spec('b1', 'B one', 'note', ['b', 'a']),
      gap('g-b', 'Gap in B', { state: 'needs-recheck', areas: ['b'] }),
      node({ id: 'plan-b', title: 'Plan B', type: 'plan', layer: 'gap', status: 'planned', path: 'plans/b.md', gap: 'g-b', areas: ['b'] }),
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
  assert.equal(v.q('#mapview').hidden, true);
  v.go('Map');
  assert.equal(v.q('#mapview').hidden, false);
  assert.equal(v.q('#view').hidden, true);
  assert.equal(v.q('#map-title').textContent, 'Spec map');
  const svg = v.q('#graph');
  const frames = () => findAll(svg, e => cls(e) === 'cluster');
  const xy = label => v.graphNode(label).attrs.transform.match(/-?[\d.]+/g).map(Number);
  const inside = (label, f) => {
    const [x, y] = xy(label), fx = +f.attrs.x, fy = +f.attrs.y;
    return x > fx && x < fx + +f.attrs.width && y > fy && y < fy + +f.attrs.height;
  };
  // spec pages only: index, run, gap and plan pages are not drawn
  assert.deepEqual(v.graphLabels().sort(), ['A one', 'A two', 'Area A', 'Area B', 'B one']);
  assert.equal(frames().length, 2);
  const frameOf = label => frames().filter(f => inside(label, f));
  for (const label of ['Area A', 'A one', 'A two', 'Area B', 'B one']) assert.equal(frameOf(label).length, 1, label + ' sits in exactly one frame');
  assert.equal(frameOf('A one')[0], frameOf('Area A')[0]);
  assert.equal(frameOf('B one')[0], frameOf('Area B')[0]);
  assert.notEqual(frameOf('Area A')[0], frameOf('Area B')[0]);
  const [f1, f2] = frames().map(f => ({ x: +f.attrs.x, y: +f.attrs.y, w: +f.attrs.width, h: +f.attrs.height }));
  assert.ok(f1.x + f1.w <= f2.x || f2.x + f2.w <= f1.x || f1.y + f1.h <= f2.y || f2.y + f2.h <= f1.y, 'frames do not overlap');
  // lines: a1-a2 (plain), a2-b1 and a-b1 (cross); membership is the frame, not a line
  const lines = () => findAll(svg, e => e.tag === 'line');
  assert.equal(lines().length, 3);
  assert.equal(lines().filter(l => cls(l) === 'cross').length, 2);
  // the area filter narrows the map
  const areaSelect = () => findAll(v.q('#map-controls'), e => e.tag === 'select')[0];
  areaSelect().value = 'b';
  areaSelect().fire('change');
  assert.deepEqual(v.graphLabels().sort(), ['Area B', 'B one']);
  areaSelect().value = '';
  areaSelect().fire('change');
  // the gap layer: gaps and plans, with the spec pages they refer to as context
  v.pill(v.q('#map-controls'), 'Gaps').click();
  assert.equal(v.q('#map-title').textContent, 'Gap map');
  assert.deepEqual(v.graphLabels().sort(), ['B one', 'Gap in B (Needs recheck)', 'Plan B (Plan)']);
  assert.ok(cls(v.graphNode('B one')).includes('context'));
  assert.ok(cls(v.graphNode('Gap in B (Needs recheck)')).includes('st-needs-recheck'));
  assert.equal(findAll(v.graphNode('Plan B (Plan)'), e => e.tag === 'rect').length, 1, 'plans are squares');
  assert.deepEqual(findAll(svg, e => cls(e) === 'cluster-label').map(text), ['Area B'], 'a frame without its area page gets a plain label');
  // a node opens its page; Back returns to the map
  v.graphNode('Gap in B (Needs recheck)').click();
  assert.equal(v.h1(), 'Gap in B');
  assert.equal(v.q('#mapview').hidden, true);
  v.q('#back').click();
  assert.equal(v.q('#mapview').hidden, false);
}

// --- search ------------------------------------------------------------------
{
  const data = parcel();
  data.files = { 'src/pickups.py': { text: 'def cancel_pickup():\n    pass', truncated: false }, 'docs/owner-rules.md': { text: '# Rules', truncated: false } };
  data.vaultPath = 'knowledge/parcel';
  const v = load(data);
  v.q('#open-search').click();
  assert.equal(v.q('#palette').hidden, false);
  assert.deepEqual(v.groups(), ['Areas'], 'before typing: somewhere to start');
  assert.deepEqual(v.resultNames(), ['Access', 'Pickups']);
  // grouped results; a title match ranks above a text match
  v.search('owner', 'typed');
  assert.deepEqual(v.groups(), ['Features', 'Files']);
  assert.deepEqual(v.resultNames(), ['Owner check', 'Cancelling a pickup', 'docs/owner-rules.md']);
  assert.deepEqual(findAll(v.q('#palette-results'), e => e.tag === 'mark').map(text), ['Owner', 'owner']);
  assert.equal(v.results()[0].attrs['aria-selected'], 'true');
  assert.equal(v.results()[0].textContent, 'Owner checkAccess', 'a feature names its area');
  // text inside a cited file is searched too
  v.search('cancel_pickup', 'typed');
  assert.deepEqual(v.resultNames(), ['Cancelling a pickup', 'src/pickups.py']);
  // gaps carry their state; superseded notes do not leak in
  v.search('p', 'typed');
  assert.deepEqual(v.groups(), ['Features', 'Gaps', 'Other pages', 'Files']);
  assert.ok(!v.resultNames().includes('Old rule'));
  assert.ok(v.results().find(r => r.textContent.startsWith('Packed pickups')).textContent.includes('Needs decision'));
  v.pill(v.q('#palette-filters'), 'Gaps').click();
  assert.deepEqual(v.groups(), ['Gaps']);
  assert.deepEqual(v.resultNames(), ['Packed pickups']);
  v.search('e', 'typed');
  assert.deepEqual(v.resultNames(), ['Closed question', 'Packed pickups'], 'the filter stays while you type');
  // arrows move, Enter opens
  v.q('#palette-input').fire('keydown', { key: 'ArrowDown' });
  assert.equal(v.results()[1].attrs['aria-selected'], 'true');
  v.q('#palette-input').fire('keydown', { key: 'ArrowDown' });
  assert.equal(v.results()[0].attrs['aria-selected'], 'true', 'wraps around');
  v.q('#palette-input').fire('keydown', { key: 'ArrowUp' });
  v.q('#palette-input').fire('keydown', { key: 'Enter' });
  assert.equal(v.q('#palette').hidden, true);
  assert.equal(v.h1(), 'Packed pickups');
  // a file opens in the file pane
  v.search('rules');
  v.results()[0].click();
  assert.equal(v.q('#filepane').hidden, false);
  assert.equal(v.q('#file-title').textContent, 'docs/owner-rules.md');
  v.q('#file-close').click();
  assert.equal(v.search('zzz').length, 0);
  assert.ok(v.q('#palette-results').textContent.includes('Nothing matches.'));
  // after reading, the empty search offers what you looked at
  v.search('', 'typed');
  assert.deepEqual(v.groups(), ['Recently viewed']);
  assert.deepEqual(v.resultNames(), ['Packed pickups']);
}

// --- copy for AI ----------------------------------------------------------------
{
  const data = parcel();
  data.vaultPath = 'knowledge/parcel';
  const v = load(data);
  const preview = () => findAll(v.q('#copy-card'), e => e.id === 'copy-preview')[0].textContent;
  const check = label => findAll(v.q('#copy-card'), e => has(e, 'check') && e.textContent === label)[0].children[0];
  v.open('Packed pickups');
  v.q('#copy-ai').click();
  assert.equal(v.q('#copydlg').hidden, false);
  assert.deepEqual(findAll(v.q('#copy-card'), e => has(e, 'pill')).map(text), ['Recheck it', 'Lay out options', 'Plan it', 'Change the spec']);
  assert.equal(preview(), [
    "Use the project-knowledge skill to re-check this gap against the code. Write the result into the gap's Recheck section and leave the decision to me.",
    '',
    'Gap: knowledge/parcel/gaps/g-open.md',
    'Title: Packed pickups',
    'State: needs decision · product gap · P1',
    '',
    'It refers to:',
    '- knowledge/parcel/notes/cancel.md (Cancelling a pickup)',
  ].join('\n'));
  // what to include
  check('The 1 spec page it refers to').checked = false;
  check('The 1 spec page it refers to').fire('change');
  assert.ok(!preview().includes('It refers to:'));
  check('Full text of the page').checked = true;
  check('Full text of the page').fire('change');
  assert.ok(preview().endsWith('Text of the page:\n\n## Current behavior\n\nRefused.'));
  // what the agent should do
  v.pill(v.q('#copy-card'), 'Plan it').click();
  assert.ok(preview().startsWith('Use the spec-change skill to plan this gap. Plan only, do not build it,'));
  v.pill(v.q('#copy-card'), 'Change the spec').click();
  assert.ok(preview().includes('What I want: [describe the change]'));
  findAll(v.q('#copy-card'), e => e.id === 'copy-do')[0].click();
  assert.deepEqual(v.copied, [preview()], 'the clipboard gets exactly the preview');
  assert.equal(v.q('#toast').textContent, 'Copied');
  v.btn(v.q('#copy-card'), 'Close').click();
  assert.equal(v.q('#copydlg').hidden, true);
  // a spec page offers what fits a spec page
  v.open('Cancelling a pickup');
  v.q('#copy-ai').click();
  assert.deepEqual(findAll(v.q('#copy-card'), e => has(e, 'pill')).map(text), ['Change this', 'Ask a question', 'Re-read against the code']);
  assert.ok(preview().includes('Page: knowledge/parcel/notes/cancel.md'));
  assert.ok(preview().includes('Related pages:\n- knowledge/parcel/notes/owner.md (Owner check)'));
  // and can go into a request instead
  v.btn(v.q('#copy-card'), 'Add to a request').click();
  assert.equal(v.q('#copydlg').hidden, true);
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Request']);
  assert.deepEqual(v.rowTitles(), ['Cancelling a pickup']);
}

// --- request: pages, what you want, a brief ---------------------------------------
{
  const data = parcel();
  data.vaultPath = 'knowledge/parcel';
  const storage = memory();
  const v = load(data, { storage });
  const brief = () => findAll(v.page(), e => e.id === 'brief')[0].textContent;
  const steps = () => findAll(v.page(), e => e.tag === 'li' && cls(e) === 'on').map(text);
  v.go('Requests');
  assert.deepEqual(v.rowTitles(), []);
  assert.ok(v.page().textContent.includes('Nothing picked yet.'));
  assert.ok(brief().includes('- [pick the pages this is about]') && brief().includes('I want: [describe the change you want]'));
  assert.deepEqual(steps(), ['Draft']);
  // pick pages through search
  v.btn(v.page(), 'Add a page').click();
  assert.equal(v.q('#palette-input').placeholder, 'Find a page to add to the request');
  assert.deepEqual(findAll(v.q('#palette-filters'), e => has(e, 'pill')).map(text), ['Everything', 'Features', 'Gaps']);
  v.search('pickup', 'typed').find(r => r.textContent.startsWith('Packed pickups')).click();
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Request'], 'picking stays on the request');
  assert.deepEqual(v.rowTitles(), ['Packed pickups']);
  v.btn(v.page(), 'Add a page').click();
  v.search('owner', 'typed')[0].click();
  assert.deepEqual(v.rowTitles(), ['Packed pickups', 'Owner check']);
  assert.deepEqual(v.nav()[4], ['Requests', '1 draft']);
  // say what you want; the brief follows as you type
  const want = () => findAll(v.page(), e => e.tag === 'textarea')[0];
  want().value = 'Let customers cancel packed pickups.';
  want().fire('input');
  assert.equal(brief(), [
    'Use the spec-change skill.',
    '',
    'I want: Let customers cancel packed pickups.',
    '',
    'This is about:',
    '- knowledge/parcel/gaps/g-open.md (Packed pickups)',
    '- knowledge/parcel/notes/owner.md (Owner check)',
    '',
    'Ask your questions first. Then edit the spec on a branch, build it and check every changed statement against the code.',
  ].join('\n'));
  v.pill(v.page(), 'Plan only').click();
  assert.ok(brief().startsWith('Use the spec-change skill to plan this change. Plan only; do not implement it.'));
  v.pill(v.page(), 'Recheck only').click();
  assert.ok(brief().startsWith('Use the project-knowledge skill to re-check these pages'));
  assert.ok(brief().endsWith('What I am wondering about: Let customers cancel packed pickups.'));
  v.pill(v.page(), 'Questions first, then build').click();
  // copying is the one tracked step
  findAll(v.page(), e => e.id === 'copy-brief')[0].click();
  assert.deepEqual(v.copied, [brief()]);
  assert.equal(steps().length, 1);
  assert.match(steps()[0], /^Brief copied on \d{4}-\d{2}-\d{2}$/);
  assert.ok(v.page().textContent.includes('Request · brief copied'));
  // the draft is kept in this browser
  const again = load(data, { storage });
  assert.deepEqual(again.nav()[4], ['Requests', '1 draft']);
  again.go('Requests');
  assert.deepEqual(again.rowTitles(), ['Packed pickups', 'Owner check']);
  assert.equal(findAll(again.page(), e => e.tag === 'textarea')[0].value, 'Let customers cancel packed pickups.');
  assert.match(findAll(again.page(), e => e.tag === 'li' && cls(e) === 'on')[0].textContent, /^Brief copied on /);
  // changing it makes it a draft again; removing and starting over
  findAll(again.page(), e => has(e, 'xbtn'))[0].click();
  assert.deepEqual(again.rowTitles(), ['Owner check']);
  assert.deepEqual(findAll(again.page(), e => e.tag === 'li' && cls(e) === 'on').map(text), ['Draft']);
  again.btn(again.page(), 'Start over').click();
  assert.deepEqual(again.rowTitles(), []);
  assert.deepEqual(again.nav()[4], ['Requests', '']);
  // a page that no longer exists is dropped, and a broken store does not stop the viewer
  storage.setItem('spec-viewer:Parcel Desk:request', JSON.stringify({ items: ['gone', 'owner'], want: 5, how: 'nonsense' }));
  const cleaned = load(data, { storage });
  cleaned.go('Requests');
  assert.deepEqual(cleaned.rowTitles(), ['Owner check']);
  storage.setItem('spec-viewer:Parcel Desk:request', '{not json');
  assert.equal(load(data, { storage }).h1(), 'Parcel Desk');
  assert.equal(load(data, { storage: { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } } }).h1(), 'Parcel Desk');
}

// --- recent changes ---------------------------------------------------------------
{
  const data = parcel();
  data.live = true;
  data.vaultPath = 'knowledge/parcel';
  data.files = { 'src/pickups.py': { text: 'x', truncated: false } };
  data.warnings = ['notes/cancel.md: changed source src/pickups.py', 'gaps/g-open.md: changed source package.json (uncommitted change, not counted)', 'notes/owner.md: something else'];
  data.nodes.find(n => n.id === 'responses').stale = true;
  data.pending = [{ path: 'notes/owner.md', status: 'changed' }, { path: 'gaps/new-one.md', status: 'added' }];
  data.history = [
    { sha: 'c3c3c3c3c3', date: '2026-11-16', subject: 'Third', more: 0, pages: [{ path: 'notes/cancel.md', status: 'changed', was: 'Old line.', now: 'New line.' }] },
    { sha: 'b2b2b2b2b2', date: '2026-11-15', subject: 'Second', more: 4, pages: [{ path: 'gaps/g-open.md', status: 'added' }, { path: 'notes/dropped.md', status: 'removed' }] },
    { sha: 'a1a1a1a1a1', date: '2026-11-14', subject: 'First', more: 0, pages: [{ path: '00-index.md', status: 'added' }] },
  ];
  const storage = memory();
  const v = load(data, { storage });
  assert.equal(v.q('#header-note').textContent, 'Spec · live from disk');
  assert.deepEqual(v.nav()[1], ['Recent changes', '3 to re-read']);
  v.go('Recent changes');
  const card = id => findAll(v.page(), e => e.id === id)[0];
  const titles = root => findAll(root, e => has(e, 'row')).map(r => (findAll(r, e => has(e, 'grow'))[0] || r).children[0].textContent);
  // pages whose sources changed, from the check warnings and the stale flag
  assert.ok(card('rereads').textContent.startsWith('3 pages need re-reading'));
  assert.deepEqual(titles(card('rereads')), ['Packed pickups', 'Cancelling a pickup', 'Responses']);
  assert.ok(card('rereads').textContent.includes('package.json'));
  assert.deepEqual(findAll(card('rereads'), e => cls(e) === 'wiki').map(text), ['src/pickups.py'], 'a cited file that was sent opens in place');
  v.btn(card('rereads'), 'Copy for AI').click();
  assert.equal(v.copied[0], [
    'Use the project-knowledge skill. These pages cite sources that changed since the last review. Re-read each page against its sources, update the text where the code now differs, and accept the fingerprints only for pages you re-read.',
    '',
    '- knowledge/parcel/gaps/g-open.md (changed: package.json)',
    '- knowledge/parcel/notes/cancel.md (changed: src/pickups.py)',
    '- knowledge/parcel/notes/responses.md',
  ].join('\n'));
  assert.equal(v.q('#toast').textContent, 'Copied 3 pages');
  // pages not committed yet
  assert.deepEqual(titles(card('pending')), ['Owner check', 'gaps/new-one.md']);
  assert.ok(card('pending').textContent.includes('New'));
  // history: commits, the pages in each, and what a summary said before and after
  const commits = () => findAll(v.page(), e => e.tag === 'article');
  const subjects = () => commits().map(c => findAll(c, e => e.tag === 'h3')[0].textContent);
  assert.deepEqual(subjects(), ['Third', 'Second', 'First']);
  assert.ok(commits()[0].textContent.startsWith('2026-11-16 · commit c3c3c3c'));
  // one line per commit: the newest starts open, the rest open on demand
  assert.deepEqual(commits().map(c => findAll(c, e => e.tag === 'details')[0].open === true), [true, false, false]);
  assert.deepEqual(commits().map(c => findAll(c, e => e.tag === 'summary')[0].textContent.replace(/^.*?(\d+ pages?)$/, '$1')), ['1 page', '6 pages', '1 page']);
  // what a summary said before and after sits behind "What changed"
  const what = findAll(commits()[0], e => cls(e) === 'what')[0];
  assert.equal(what.children[0].textContent, 'What changed');
  assert.deepEqual(findAll(what, e => has(e, 'wasnow'))[0].children.map(text), ['wasOld line.', 'nowNew line.']);
  // pages are sorted into spec and gaps, each row saying what happened to the page
  assert.deepEqual(titles(commits()[1]), ['notes/dropped.md', 'Packed pickups', 'and 4 more pages']);
  assert.deepEqual(findAll(commits()[1], e => has(e, 'group')).map(text), ['Spec pages · 1', 'Gaps and plans · 1']);
  assert.deepEqual(findAll(commits()[1], e => has(e, 'tag')).map(text), ['Removed', 'New']);
  assert.deepEqual(findAll(commits()[0], e => has(e, 'group')), [], 'no label for a single group');
  assert.ok(commits()[1].textContent.includes('New') && commits()[1].textContent.includes('Removed'));
  assert.deepEqual(titles(commits()[2]), ['Index page']);
  // a page in the history opens
  v.btn(commits()[0], 'Cancelling a pickup').click();
  assert.equal(v.h1(), 'Cancelling a pickup');
  v.q('#back').click();
  v.btn(card('rereads'), 'Responses').click();
  assert.ok(v.page().textContent.includes('Sources changed since the last review'));
  v.q('#back').click();
  // filters
  v.pill(v.page(), 'Gaps').click();
  assert.deepEqual(titles(card('rereads')), ['Packed pickups']);
  assert.deepEqual(titles(card('pending')), ['gaps/new-one.md']);
  assert.deepEqual(subjects(), ['Second']);
  assert.deepEqual(titles(commits()[0]), ['Packed pickups'], 'the "more" line belongs to the unfiltered list');
  v.pill(v.page(), 'Spec pages').click();
  assert.deepEqual(subjects(), ['Third', 'Second']);
  assert.ok(!v.pill(v.page(), 'Since my last visit'), 'nothing is new on a first visit');

  // on a later visit, commits newer than the last one seen are marked
  assert.equal(storage.getItem('spec-viewer:Parcel Desk:seen'), '"c3c3c3c3c3"');
  storage.setItem('spec-viewer:Parcel Desk:seen', '"a1a1a1a1a1"');
  data.warnings = [];
  data.nodes.find(n => n.id === 'responses').stale = false;
  const later = load(data, { storage });
  assert.deepEqual(later.nav()[1], ['Recent changes', '2 new']);
  later.go('Recent changes');
  assert.equal(findAll(later.page(), e => e.id === 'rereads').length, 0);
  later.pill(later.page(), 'Since my last visit').click();
  const fresh = findAll(later.page(), e => e.tag === 'article');
  assert.deepEqual(fresh.map(c => findAll(c, e => e.tag === 'h3')[0].textContent), ['Third', 'Second']);
  assert.ok(fresh[0].textContent.includes('· new'));

  // without the serve command there is no history, and the page says so
  const bare = load(parcel());
  bare.go('Recent changes');
  assert.ok(bare.page().textContent.includes('History is shown when the spec is opened with the serve command.'));
  data.history = [];
  const empty = load(data);
  empty.go('Recent changes');
  assert.ok(empty.page().textContent.includes('No Git history was found for this vault.'));
}

// --- cited files open inside the viewer ---------------------------------------------
{
  const v = load({
    title: 'Files', live: true, vaultPath: 'knowledge/demo',
    files: {
      'docs/plan.md': { text: '# Plan\n\n| Task | Status |\n| --- | :-- |\n| CJ-01 — notes | Done \\| ok |\n| `a|b` | [[notes/n|N]] | extra |\n\nSee [code](../src/a.py#L2) and [web](https://example.com).', truncated: false },
      'src/a.py': { text: 'one\ntwo\nthree', truncated: true },
    },
    nodes: [
      spec('a', 'Area', 'area', []),
      spec('n', 'N', 'note', ['a'], {
        summary: 'Plain words.', sources: ['src/a.py', 'src/missing.py'],
        body: '[plan](../../../docs/plan.md#L3) and [raw](<../../../src/a.py#L2-L3>) and [gone](../../../docs/none.md) and [up](../../../../outside.md)',
      }),
    ],
    edges: [{ source: 'a', target: 'n' }],
  });
  v.open('N');
  const fileLinks = findAll(v.article(), e => e.tag === 'button' && cls(e) === 'wiki');
  assert.deepEqual(fileLinks.map(text), ['plan', 'raw']);
  assert.deepEqual(findAll(v.article(), e => e.tag === 'a').map(text), ['gone', 'up'], 'files that were not sent stay ordinary links');
  const pane = v.q('#filepane'), body = v.q('#file-body');
  const rows = () => findAll(body, e => has(e, 'ln'));
  const hits = () => rows().filter(e => has(e, 'hit')).map(e => findAll(e, x => cls(x) === 'txt')[0].textContent);
  const actions = () => findAll(v.q('#file-actions'), e => e.tag === 'button');
  // a Markdown document opens rendered, with its table
  fileLinks[0].click();
  assert.equal(pane.hidden, false);
  assert.equal(v.q('#file-title').textContent, 'docs/plan.md');
  assert.equal(v.q('#file-note').textContent, 'Line 3 · Read from disk when this page loaded');
  assert.deepEqual(actions().map(e => [e.textContent, e.attrs['aria-pressed']]), [['Document', 'true'], ['Source lines', 'false']]);
  assert.deepEqual(findAll(body, e => e.tag === 'th').map(text), ['Task', 'Status']);
  assert.deepEqual(findAll(body, e => e.tag === 'td').map(text), ['CJ-01 — notes', 'Done | ok', 'a|b', 'N']);
  // its source lines, with the cited line marked
  actions()[1].click();
  assert.equal(rows().length, 8);
  assert.deepEqual(hits(), ['| Task | Status |']);
  actions()[0].click();
  // links inside the document resolve from the document's own folder
  findAll(body, e => e.tag === 'button' && cls(e) === 'wiki').find(e => e.textContent === 'code').click();
  assert.equal(v.q('#file-title').textContent, 'src/a.py');
  assert.equal(v.q('#file-note').textContent, 'Line 2 · Read from disk when this page loaded · only the beginning of the file is shown');
  assert.deepEqual(rows().map(text), ['1one', '2two', '3three']);
  assert.deepEqual(hits(), ['two']);
  v.q('#file-close').click();
  assert.equal(pane.hidden, true);
  fileLinks[1].click();
  assert.deepEqual(hits(), ['two', 'three']);
  pane.fire('keydown', { key: 'Escape' });
  assert.equal(pane.hidden, true);
  // the page's source list opens the same way
  const sources = findAll(v.page(), e => e.tag === 'details').find(d => d.textContent.startsWith('Source files (2)'));
  assert.deepEqual(findAll(sources, e => e.tag === 'button').map(text), ['src/a.py']);
  assert.ok(sources.textContent.includes('src/missing.py'));
  findAll(sources, e => e.tag === 'button')[0].click();
  assert.equal(v.q('#file-title').textContent, 'src/a.py');
  assert.deepEqual(hits(), []);
}

// --- Markdown rendering ----------------------------------------------------------
function article(body) {
  const v = load({ title: 'Md', nodes: [
    node({ id: 'n', title: 'N', type: 'note', layer: 'spec', status: 'current', path: 'notes/n.md', areas: [], body }),
    node({ id: 'l', title: 'Legacy', type: 'note', layer: 'spec', status: 'current', path: 'notes/legacy.md', areas: [] }),
  ], edges: [] });
  assert.deepEqual(v.tree(), ['Legacy', 'N'], 'notes without an area are still in the tree');
  v.treeRow('N').click();
  return { v, art: v.article() };
}
const pres = art => findAll(art, e => e.tag === 'pre').map(text);

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
  assert.deepEqual(wiki.map(text), ['Alias', 'Plain']);
  wiki[0].click();
  assert.equal(v.h1(), 'Legacy', 'escaped pipe resolves to notes/legacy');
}
{
  // inline formatting and hostile text
  const { art } = article('**[[notes/legacy|label]]** and **[source](https://example.com)** and **`code`**');
  const strongs = findAll(art, e => e.tag === 'strong');
  assert.equal(findAll(strongs[0], e => e.tag === 'button').length, 1);
  assert.equal(findAll(strongs[1], e => e.tag === 'a')[0].href, 'https://example.com/');
  assert.equal(findAll(strongs[2], e => e.tag === 'code').length, 1);
  const hostile = article('<img src=x onerror=alert(1)> [bad](javascript:alert) [ok](mailto:a@b.c)\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nnot | a table').art;
  assert.equal(findAll(hostile, e => e.tag === 'img').length, 0);
  assert.deepEqual(findAll(hostile, e => e.tag === 'a').map(e => e.href), ['mailto:a@b.c']);
  assert.ok(hostile.textContent.includes('<img src=x onerror=alert(1)>'));
  assert.deepEqual(findAll(hostile, e => e.tag === 'td').map(text), ['1', '2']);
  assert.ok(findAll(hostile, e => e.tag === 'p').some(e => e.textContent === 'not | a table'));
}

console.log('PASS: viewer navigation, pages, gaps, map, search, copy, requests, changes, cited files, Markdown');
