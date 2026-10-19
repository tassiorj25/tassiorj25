/**
 * The decisions capture.mjs makes before it touches a page, kept separate from
 * the browser so they can be tested on their own: whether robots.txt permits a
 * path, and how a JSON body is reduced to a shape.
 */

/** Minimal robots.txt matcher: longest-match Allow/Disallow for the chosen group. */
export function robotsVerdict(robotsTxt, pathname, agent = '*') {
  const groups = new Map();
  let current = [];
  let lastWasAgent = false;
  for (const raw of (robotsTxt || '').split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trim();
    if (!line) continue;
    const m = line.match(/^([A-Za-z-]+)\s*:\s*(.*)$/);
    if (!m) continue;
    const field = m[1].toLowerCase();
    const value = m[2].trim();
    if (field === 'user-agent') {
      // Consecutive User-agent lines share one rule block.
      if (!lastWasAgent) current = [];
      current.push(value.toLowerCase());
      for (const ua of current) if (!groups.has(ua)) groups.set(ua, []);
      lastWasAgent = true;
    } else if (field === 'allow' || field === 'disallow') {
      lastWasAgent = false;
      for (const ua of current) groups.get(ua).push({ type: field, value });
    } else {
      lastWasAgent = false;
    }
  }

  const rules = groups.get(agent.toLowerCase()) || groups.get('*') || [];
  let best = null;
  for (const rule of rules) {
    if (rule.type === 'disallow' && rule.value === '') continue; // empty Disallow allows all
    if (!matchesRobotsPattern(rule.value, pathname)) continue;
    const weight = rule.value.replace(/\*/g, '').length;
    // Longest match wins; Allow wins a tie, as the spec's examples do.
    if (!best || weight > best.weight || (weight === best.weight && rule.type === 'allow')) {
      best = { type: rule.type, weight, value: rule.value };
    }
  }
  if (!best) return { allowed: true, rule: null };
  return { allowed: best.type === 'allow', rule: `${best.type}: ${best.value}` };
}

export function matchesRobotsPattern(pattern, pathname) {
  if (pattern === '') return false;
  const anchored = pattern.endsWith('$');
  const body = anchored ? pattern.slice(0, -1) : pattern;
  const rx = body.split('*').map((s) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*');
  return new RegExp('^' + rx + (anchored ? '$' : '')).test(pathname);
}

/**
 * Reduce a JSON value to its shape. Keys and types survive; content does not,
 * so a payload's values never reach disk.
 */
export function jsonShape(value, depth = 0) {
  if (depth > 6) return '…';
  if (value === null) return 'null';
  if (Array.isArray(value)) {
    if (value.length === 0) return ['empty'];
    return [jsonShape(value[0], depth + 1), `×${value.length}`];
  }
  const t = typeof value;
  if (t === 'object') {
    const out = {};
    for (const k of Object.keys(value).slice(0, 80)) out[k] = jsonShape(value[k], depth + 1);
    return out;
  }
  if (t === 'string') {
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) return 'string<date>';
    if (/^https?:\/\//.test(value)) return 'string<url>';
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(value)) return 'string<uuid>';
    return 'string';
  }
  return t;
}
