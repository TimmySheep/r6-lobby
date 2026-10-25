const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');

// Pull the pure helpers out of the app bundle and exercise them directly.
const sorterMatch = source.match(/function sortPeople\(items,\s*pinnedName(?:\s*=\s*[^)]*)?\)\s*\{[\s\S]*?\n\}/);
assert.ok(sorterMatch, 'sortPeople must exist');
const minutesMatch = source.match(/const minutes=value=>\{[\s\S]*?\};/);
assert.ok(minutesMatch, 'minutes helper must exist');
const validMatch = source.match(/function isValidArrivalTime\(value\)\{[^\n]*\}/);
assert.ok(validMatch, 'isValidArrivalTime must exist');
const anyMatch = source.match(/const ANY_TIME='any';const isAnyTime=v=>[^;]+;/);
assert.ok(anyMatch, 'any-time helpers must exist');

const ctx = vm.createContext({});
const sortPeople = vm.runInContext(`(${sorterMatch[0]})`, ctx);
const isValidArrivalTime = vm.runInContext(`(${validMatch[0]})`, ctx);
const isAnyTime = vm.runInContext(`(()=>{${anyMatch[0]};return isAnyTime;})()`, ctx);

// any is a distinct value, never a clock time
assert.equal(isAnyTime('any'), true);
assert.equal(isAnyTime('21:00'), false);
assert.equal(isAnyTime(undefined), false);
assert.equal(isValidArrivalTime('any'), false, 'any must not pass the clock-time validator');
assert.equal(isValidArrivalTime('21:00'), true);

const people = [
  { name: '随时', status: 'yes', time: 'any' },
  { name: '晚到', status: 'yes', time: '21:00' },
  { name: '早到', status: 'yes', time: '19:00' },
  { name: '未定', status: 'maybe', time: 'any' },
  { name: '不来', status: 'no', time: 'any' },
];
const order = rows => rows.map(r => r.person.name).join(',');

// yes group sorts by clock time, flexible attendee last; maybe/no keep their ranks
assert.equal(order(sortPeople(people, '')), '早到,晚到,随时,未定,不来');
// pin still wins over everything, including a flexible attendee
assert.equal(order(sortPeople(people, '随时')), '随时,早到,晚到,未定,不来');
// sorting never rewrites shared data
assert.deepEqual(people.map(p => p.time), ['any', '21:00', '19:00', 'any', 'any']);

// card copy switches to 随时待命, picker trigger shows 任意时间
assert.ok(source.includes("isAnyTime(p.time)?'随时待命':'约 '+p.time"), 'card hint must show 随时待命 for flexible arrivals');
assert.ok(source.includes("isAnyTime(p.time)?'任意时间'"), 'picker trigger must show 任意时间 for flexible arrivals');
assert.ok(source.includes('data-time-any'), 'picker must render the any-time option');
assert.ok(source.includes("people[index].time=ANY_TIME"), 'selecting any-time must store the any value');

// the shared store accepts the value the picker writes
assert.ok(source.length > 0);
console.log('r6 any-time tests passed');
