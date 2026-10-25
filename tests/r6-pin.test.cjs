const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');
const sorterMatch = source.match(/function sortPeople\(items,\s*pinnedName(?:\s*=\s*[^)]*)?\)\s*\{[\s\S]*?\n\}/);
assert.ok(sorterMatch, 'sortPeople must accept the browser-local pinned name');
const storageMatch = source.match(/function readPinnedPerson\(storage\)\s*\{[\s\S]*?\n\}/);
assert.ok(storageMatch, 'local pinned preference reader must exist');
const writerMatch = source.match(/function writePinnedPerson\(storage,\s*name\)\s*\{[\s\S]*?\n\}/);
assert.ok(writerMatch, 'local pinned preference writer must exist');
const uniqueMatch = source.match(/function isUniquePersonName\(items,\s*name\)\s*\{[^}]*\}/);
assert.ok(uniqueMatch, 'pin identity must reject ambiguous duplicate names');
const sorterContext = vm.createContext({});
const sortPeople = vm.runInContext(`(${sorterMatch[0]})`, sorterContext);
const storageContext = vm.createContext({});
const readPinnedPerson = vm.runInContext(`const PINNED_PERSON_KEY='r6-pinned-person'; (${storageMatch[0]})`, storageContext);
const writerContext = vm.createContext({});
const writePinnedPerson = vm.runInContext(`const PINNED_PERSON_KEY='r6-pinned-person'; (${writerMatch[0]})`, writerContext);
const uniqueContext = vm.createContext({});
const isUniquePersonName = vm.runInContext(`(${uniqueMatch[0]})`, uniqueContext);

const people = [
  { name: '晚到', status: 'yes', time: '20:00' },
  { name: '早到', status: 'yes', time: '19:00' },
  { name: '未定', status: 'maybe', time: '18:00' },
  { name: '不来', status: 'no', time: '17:00' },
];
assert.equal(Array.from(sortPeople(people, '不来'), row => row.index).join(','), '3,1,0,2', 'pinned member leads the list without disturbing the existing order of others');
assert.equal(Array.from(sortPeople(people, '晚到'), row => row.index).join(','), '0,1,2,3', 'pinned attendee leads even when they are not earliest');
assert.equal(Array.from(sortPeople(people, 'missing'), row => row.index).join(','), '1,0,2,3', 'stale pin falls back to normal status/time sorting');
assert.deepEqual(people.map(p => p.name), ['晚到', '早到', '未定', '不来'], 'pin sorting never mutates shared people data');
assert.equal(isUniquePersonName(people, '晚到'), true);
assert.equal(isUniquePersonName([...people, { name: '晚到' }], '晚到'), false, 'ambiguous names must not pin multiple people');

const values = new Map();
const storage = {
  getItem: key => values.has(key) ? values.get(key) : null,
  setItem: (key, value) => values.set(key, String(value)),
  removeItem: key => values.delete(key),
};
assert.equal(writePinnedPerson(storage, 'Timmy'), true);
assert.equal(readPinnedPerson(storage), 'Timmy');
assert.equal(writePinnedPerson(storage, ''), true, 'empty pin clears preference');
assert.equal(readPinnedPerson(storage), '');
assert.equal(writePinnedPerson({ setItem() { throw Error('disabled'); } }, 'Timmy'), false, 'storage failure must not crash the board');

for (const expected of ['data-pin=', 'aria-pressed=', '固定到顶部', '取消置顶', '同名队友无法区分，请先修改昵称再固定。']) assert.ok(source.includes(expected), `UI must provide accessible pin toggle: ${expected}`);
const pinMarkupIndex = source.indexOf('class="pin-person');
const editMarkupIndex = source.indexOf('class="edit-person');
assert.ok(pinMarkupIndex >= 0 && editMarkupIndex > pinMarkupIndex, 'pin icon must be directly before the pencil action');
assert.ok(source.includes("'r6-pinned-person'"), 'preference key must be isolated to this browser');
assert.ok(source.includes('writePinnedPerson(window.localStorage,'), 'pin changes must persist locally');
console.log('PASS: per-browser pin persistence, top ordering, fallback sorting, data preservation and accessible toggle contract');
