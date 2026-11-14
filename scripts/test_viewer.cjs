// Focused DOM-stub checks for inline rendering; run with Node, no dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const template = fs.readFileSync(path.join(__dirname, '../skills/project-knowledge/assets/viewer.html'), 'utf8');
const start = template.indexOf('        function inline(parent, text, n) {');
const end = template.indexOf('        function markdown(body, n) {', start);
assert.ok(start >= 0 && end > start, 'inline renderer must exist');
function element(tag, text) {
  return { tag, children: text === undefined ? [] : [{ text }], append(...nodes) { this.children.push(...nodes); }, addEventListener() {} };
}
const context = {
  document: { createTextNode: text => ({ text }) },
  el: element,
  resolveWiki: () => ({ id: 'example' }),
  safeHref: raw => raw.startsWith('https://') ? raw : null,
  openNode() {},
};
vm.createContext(context);
vm.runInContext(template.slice(start, end), context);
function render(text) {
  const parent = element('div');
  context.inline(parent, text, {});
  return parent.children.find(child => child.tag === 'strong');
}
assert.equal(render('**[[notes/example|label]]**').children[1].tag, 'button');
const link = render('**[source](https://example.com)**').children[1];
assert.equal(link.tag, 'a');
assert.equal(link.href, 'https://example.com');
assert.equal(render('**`code`**').children[1].tag, 'code');
assert.equal(render('**<img src=x onerror=alert(1)>**').children[0].text, '<img src=x onerror=alert(1)>');
const unsafe = render('**[bad](javascript:alert)**');
assert.ok(unsafe.children.every(child => !child.tag));
console.log('PASS: bold inline links, code and hostile text');
