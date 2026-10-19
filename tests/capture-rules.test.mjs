import assert from 'node:assert/strict';
import test from 'node:test';
import { jsonShape, matchesRobotsPattern, robotsVerdict } from '../tools/capture-rules.mjs';

test('an empty or absent robots.txt allows everything', () => {
  assert.equal(robotsVerdict('', '/anything').allowed, true);
  assert.equal(robotsVerdict(null, '/anything').allowed, true);
});

test('a bare Disallow: / blocks the whole site', () => {
  const v = robotsVerdict('User-agent: *\nDisallow: /', '/pricing');
  assert.equal(v.allowed, false);
  assert.equal(v.rule, 'disallow: /');
});

test('an empty Disallow value allows everything', () => {
  assert.equal(robotsVerdict('User-agent: *\nDisallow:', '/anything').allowed, true);
});

test('a path outside the disallowed prefix stays allowed', () => {
  const txt = 'User-agent: *\nDisallow: /admin';
  assert.equal(robotsVerdict(txt, '/admin/users').allowed, false);
  assert.equal(robotsVerdict(txt, '/about').allowed, true);
});

test('the longest matching rule wins, so Allow can carve out a subtree', () => {
  const txt = 'User-agent: *\nDisallow: /app\nAllow: /app/public';
  assert.equal(robotsVerdict(txt, '/app/private').allowed, false);
  assert.equal(robotsVerdict(txt, '/app/public/page').allowed, true);
});

test('Allow wins an equal-length tie', () => {
  const txt = 'User-agent: *\nDisallow: /x\nAllow: /x';
  assert.equal(robotsVerdict(txt, '/x').allowed, true);
});

test('comments and blank lines are ignored', () => {
  const txt = '# site rules\n\nUser-agent: *   # everyone\nDisallow: /secret\n';
  assert.equal(robotsVerdict(txt, '/secret/x').allowed, false);
});

test('a named agent group takes precedence over the wildcard group', () => {
  const txt = 'User-agent: *\nDisallow: /\n\nUser-agent: GoodBot\nDisallow: /admin';
  assert.equal(robotsVerdict(txt, '/page', 'GoodBot').allowed, true);
  assert.equal(robotsVerdict(txt, '/admin', 'GoodBot').allowed, false);
  assert.equal(robotsVerdict(txt, '/page').allowed, false);
});

test('consecutive User-agent lines share one rule block', () => {
  const txt = 'User-agent: A\nUser-agent: B\nDisallow: /no';
  assert.equal(robotsVerdict(txt, '/no', 'A').allowed, false);
  assert.equal(robotsVerdict(txt, '/no', 'B').allowed, false);
});

test('an unknown agent falls back to the wildcard group', () => {
  const txt = 'User-agent: *\nDisallow: /x\n\nUser-agent: Other\nDisallow:';
  assert.equal(robotsVerdict(txt, '/x', 'BlueprintBot').allowed, false);
});

test('wildcards and end-anchors in patterns are honoured', () => {
  assert.equal(matchesRobotsPattern('/*.json', '/data/a.json'), true);
  assert.equal(matchesRobotsPattern('/*.json$', '/data/a.json'), true);
  assert.equal(matchesRobotsPattern('/*.json$', '/data/a.json?x=1'), false);
  assert.equal(matchesRobotsPattern('/a', '/b'), false);
  assert.equal(matchesRobotsPattern('', '/a'), false);
});

test('a regex metacharacter in a pattern is matched literally', () => {
  assert.equal(matchesRobotsPattern('/a+b', '/a+b/c'), true);
  assert.equal(matchesRobotsPattern('/a+b', '/aaab'), false);
});

test('jsonShape keeps keys and types but never values', () => {
  const shape = jsonShape({ id: 42, name: 'Ada Lovelace', email: 'ada@example.com' });
  assert.deepEqual(shape, { id: 'number', name: 'string', email: 'string' });
  assert.equal(JSON.stringify(shape).includes('Ada'), false);
});

test('jsonShape labels dates, urls and uuids without revealing them', () => {
  assert.equal(jsonShape('2026-10-19T00:00:00Z'), 'string<date>');
  assert.equal(jsonShape('https://target.test/secret-path'), 'string<url>');
  assert.equal(jsonShape('550e8400-e29b-41d4-a716-446655440000'), 'string<uuid>');
});

test('jsonShape describes an array by its first item and length', () => {
  assert.deepEqual(jsonShape([{ a: 1 }, { a: 2 }, { a: 3 }]), [{ a: 'number' }, '×3']);
  assert.deepEqual(jsonShape([]), ['empty']);
});

test('jsonShape handles null, booleans and nesting', () => {
  assert.equal(jsonShape(null), 'null');
  assert.equal(jsonShape(true), 'boolean');
  assert.deepEqual(jsonShape({ a: { b: { c: 1 } } }), { a: { b: { c: 'number' } } });
});

test('jsonShape stops descending instead of recursing forever', () => {
  let deep = 1;
  for (let i = 0; i < 12; i++) deep = { n: deep };
  assert.equal(JSON.stringify(jsonShape(deep)).includes('…'), true);
});

test('jsonShape caps the number of keys it records', () => {
  const wide = {};
  for (let i = 0; i < 200; i++) wide[`k${i}`] = i;
  assert.equal(Object.keys(jsonShape(wide)).length, 80);
});
