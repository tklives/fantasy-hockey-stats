#!/usr/bin/env python3
"""
build_page.py - turn every data/week_N.json into one static page, site/index.html.

No server and no network needed: the data is embedded in the page, so you can double-click the
file to open it, or drop the site/ folder on any web host. Run it after espn_weekly_pull.py.

    python build_page.py                        # reads data/, writes site/index.html
    python build_page.py some/data some/site    # same, for other folders (handy for testing)
"""
import datetime as dt
import json
import sys
from pathlib import Path

LEAGUE_NAME = "My 2027 League"
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
SITE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("site")

# __DATA__ and __GENERATED__ are swapped in below with str.replace (not an f-string,
# because the CSS and JS are full of braces).
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fantasy Hockey Stats</title>
<style>
  :root {
    --bg: #f6f7f9; --card: #fff; --row: #eceff3; --text: #1b1f24; --muted: #6a737d; --line: #e1e4e8;
    --pos: 34, 160, 90; --neg: 220, 60, 60; --accent: #b45309; --red: #c93636;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f1318; --card: #171c23; --row: #212935; --text: #e6e9ee; --muted: #8b95a1; --line: #2a313a;
      --accent: #f0a35a; --red: #ff7b7b;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 16px; background: var(--bg); color: var(--text);
         font: 15px/1.4 system-ui, sans-serif; }
  main { max-width: 1240px; margin: 0 auto; }
  header.top { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end;
               gap: 16px 24px; padding: 12px 0 20px; margin-bottom: 20px; border-bottom: 1px solid var(--line); }
  h1 { font-size: 26px; line-height: 1.15; letter-spacing: -.01em; margin: 0; }
  .brand .sub { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
  .controls { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
  .stepper { display: inline-flex; align-items: stretch; background: var(--card);
             border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
  .stepper > * { font: inherit; color: var(--text); background: transparent; border: 0; padding: 7px 12px; cursor: pointer; }
  .stepper > * + * { border-left: 1px solid var(--line); }
  .stepper select { font-weight: 600; padding-right: 8px; }
  .stepper button { font-size: 18px; line-height: 1; padding: 7px 14px; }
  .stepper button:hover:not(:disabled) { background: var(--row); }
  .stepper button:disabled { opacity: .3; cursor: default; }
  .range { color: var(--muted); font-size: 14px; }
  h2 { font-size: 16px; margin: 0; }
  select, .btn { font: inherit; padding: 4px 10px; background: var(--card); color: var(--text);
                 border: 1px solid var(--line); border-radius: 6px; cursor: pointer; }
  .muted { color: var(--muted); }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; font-size: 13px;
            color: var(--muted); margin: 0 0 20px; }
  .sw { display: inline-block; width: 22px; height: 14px; vertical-align: middle; margin-right: 4px;
        border-radius: 3px; background: rgba(var(--pos), .35); }
  .sw.ir { background: transparent;
           background-image: repeating-linear-gradient(135deg, transparent 0 4px, rgba(180,83,9,.45) 4px 6px); }
  .ex { font-weight: 600; margin-right: 3px; }
  .ex.ben { color: var(--accent); }
  .ex.down { color: var(--red); }
  .sw.absent { background: repeating-linear-gradient(135deg, transparent 0 4px, var(--line) 4px 5px);
               border: 1px solid var(--line); }
  .sw.future { background: rgba(128, 128, 128, .15); border: 1px dashed var(--line); }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
          padding: 12px; margin-bottom: 16px; }
  .card-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
               justify-content: space-between; margin-bottom: 8px; }
  /* Sideways scroll for narrow screens only. Setting one axis to auto makes the other auto too, so a
     sub-pixel height overflow would show a vertical scrollbar; hide that axis explicitly. */
  .scroll { overflow-x: auto; overflow-y: hidden; }

  .top-grid { display: flex; flex-wrap: wrap; gap: 16px; align-items: stretch; margin-bottom: 16px; }
  .top-grid .card { margin-bottom: 0; }
  .bench-card { flex: 0 1 440px; min-width: 300px; }
  .misses-card { flex: 1 1 400px; min-width: 300px; }
  table.misses td { padding: 4px 8px; vertical-align: middle; white-space: nowrap; }
  table.misses tr.miss { cursor: pointer; border-top: 1px solid var(--line); }
  table.misses tr.miss:first-child { border-top: 0; }
  table.misses tr.miss:hover td { background: var(--row); }
  table.misses td.pt { width: 56px; text-align: right; font-weight: 700; font-size: 16px; color: var(--accent); font-variant-numeric: tabular-nums; }
  table.misses td.who { text-align: left; white-space: normal; }
  table.misses td.who .tag { margin-left: 6px; }
  table.misses td.team { text-align: left; font-weight: 600; white-space: normal; }
  table.misses td.day { text-align: right; color: var(--muted); font-size: 13px; }
  .seg { display: inline-flex; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
  .seg button { font: inherit; font-size: 13px; padding: 3px 10px; background: transparent; color: var(--muted); border: 0; cursor: pointer; }
  .seg button + button { border-left: 1px solid var(--line); }
  .seg button[aria-pressed="true"] { background: var(--row); color: var(--text); font-weight: 600; }
  table.bench th, table.bench td { padding: 5px 12px; }
  table.bench th:nth-child(1), table.bench td:nth-child(1) { width: 36px; text-align: right; color: var(--muted); padding-left: 4px; }
  table.bench th:nth-child(2), table.bench td:nth-child(2) { text-align: left; }
  table.bench tbody tr { border-top: 1px solid var(--line); }
  table.bench tbody tr:hover td { background: var(--row); }
  table.bench td.num { font-variant-numeric: tabular-nums; }
  table.bench td.num.bn { color: var(--accent); font-weight: 600; }
  button.sort { all: unset; cursor: pointer; color: inherit; font: inherit; padding: 2px 0; }
  button.sort:focus-visible { outline: 2px solid var(--muted); border-radius: 4px; }
  th.sorted button.sort { color: var(--text); font-weight: 600; }
  th.sorted.desc button.sort::after { content: ' \25BC'; font-size: 9px; }
  th.sorted.asc button.sort::after { content: ' \25B2'; font-size: 9px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 3px 5px; text-align: right; white-space: nowrap; vertical-align: top; }
  th { font-weight: 500; color: var(--muted); font-size: 13px; }
  th:first-child, td:first-child { text-align: left; }

  /* The matchup table: fixed layout so every day column is the same width all week. */
  table.ov { table-layout: fixed; min-width: 860px; }
  table.ov col.name { width: 190px; }
  table.ov col.tot { width: 92px; }
  table.ov th:first-child, table.ov td:first-child { position: sticky; left: 0; z-index: 1; background: var(--card); }
  th.future { opacity: .45; }
  th.today { color: var(--text); font-weight: 600; box-shadow: inset 0 -2px 0 var(--accent); }
  td.future { background: rgba(128, 128, 128, .08); color: var(--muted); opacity: .6; text-align: center; vertical-align: middle; }

  tr.teamrow { cursor: pointer; }
  tr.teamrow td { background: var(--row); padding-top: 6px; padding-bottom: 6px; vertical-align: middle; }
  tr.teamrow td.future { background: var(--row); }
  tr.teamrow:hover td { filter: brightness(.97); }
  .tg { all: unset; cursor: pointer; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
  .tg:focus-visible { outline: 2px solid var(--muted); border-radius: 4px; }
  .tg .chev::before { content: '\25B8'; color: var(--muted); }
  tbody.open .tg .chev::before { content: '\25BE'; }
  tbody.team:not(.open) tr.prow { display: none; }
  .winner::after { content: '\25B2'; margin-left: 6px; font-size: 10px; color: rgb(var(--pos)); }
  tr.prow td:first-child { padding-left: 24px; white-space: normal; }
  tr.prow td { border-top: 1px solid var(--line); padding-top: 1px; padding-bottom: 1px; vertical-align: middle; }
  .pname { margin-right: 6px; }
  .ppos { font-size: 11px; color: var(--muted); }
  .note { display: block; font-size: 11px; line-height: 1.2; }
  .note span + span { margin-left: 8px; }
  .note .add { color: rgb(var(--pos)); }
  .note .drop { color: var(--red); }

  .cell { display: block; width: 100%; padding: 4px 6px; border: 0; border-radius: 6px;
          font: inherit; color: inherit; text-align: right; background-color: transparent; }
  button.cell { cursor: pointer; }
  button.cell:hover, button.cell:focus-visible { outline: 2px solid var(--muted); }
  .cell.pos { background-color: rgba(var(--pos), var(--a)); }
  .cell.neg { background-color: rgba(var(--neg), var(--a)); }
  .cell small { display: block; font-size: 11px; color: var(--muted); }
  .cell small.left { color: var(--accent); }
  .total { font-weight: 600; }
  .total small { display: block; font-weight: 400; font-size: 11px; color: var(--muted); }
  .total small.tt { font-style: italic; line-height: 1.05; }
  tr.prow td.total { line-height: 1.15; }
  .total .bn { color: var(--accent); }
  .total .bn.zero { color: var(--muted); font-weight: 400; }

  .pc { padding: 1px 6px; }
  .pc .top { display: flex; justify-content: flex-end; align-items: baseline; gap: 4px; line-height: 1.2; }
  .pc .pt { font-variant-numeric: tabular-nums; }
  .pc.ir { background-image: repeating-linear-gradient(135deg, transparent 0 5px, rgba(180,83,9,.25) 5px 7px); }
  .pc.ben .pt { color: var(--accent); font-weight: 600; }
  .pc.down .pt { color: var(--red); font-weight: 600; }
  .pc.quiet .pt { color: var(--muted); }
  .pc .sl { display: block; font-size: 10px; line-height: 1.1; color: var(--muted);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: right; }
  .tag { font-size: 10px; padding: 0 4px; border-radius: 4px; border: 1px solid var(--line); color: var(--muted); }
  .tag.dnp { color: rgb(var(--neg)); border-color: rgba(var(--neg), .5); }
  td.absent { background-image: repeating-linear-gradient(135deg, transparent 0 5px, var(--line) 5px 6px); }

  dialog { width: min(640px, calc(100vw - 32px)); background: var(--card); color: var(--text);
           border: 1px solid var(--line); border-radius: 10px; padding: 16px; }
  dialog::backdrop { background: rgba(0, 0, 0, .5); }
  .close { float: right; }
  @media (max-width: 700px) { .pc .sl { display: none; } }
</style>
</head>
<body>
<main>
  <header class="top">
    <div class="brand">
      <h1>Fantasy Hockey Stats</h1>
      <p class="sub">__LEAGUE__ &middot; head-to-head points</p>
    </div>
    <div class="controls">
      <div class="stepper" role="group" aria-label="Choose a week">
        <button id="week-prev" aria-label="Previous week">&#8249;</button>
        <select id="week-select" aria-label="Week"></select>
        <button id="week-next" aria-label="Next week">&#8250;</button>
      </div>
      <span class="range" id="week-range"></span>
      <button class="btn" id="toggle-all">Expand all teams</button>
    </div>
  </header>
  <p class="legend">
    <span><b class="ex">1.2</b>Active (counted)</span>
    <span><b class="ex ben">1.2</b><span class="tag">BE</span> Bench (not counted)</span>
    <span><span class="sw ir"></span><b class="ex ben">1.2</b><span class="tag">IR</span> IR (not counted)</span>
    <span><b class="ex down">-1.2</b>Negative</span>
    <span><span class="sw absent"></span>Not on roster</span>
    <span><span class="sw future"></span>Not played yet</span>
    <span>&ndash; no game</span>
    <span><span class="tag dnp">DNP</span> team played, player didn't</span>
    <span><span class="tag dnp">O</span> <span class="tag dnp">DTD</span> out / day-to-day today (as of last update)</span>
  </p>
  <div id="week"></div>
  <p class="muted">Updated <time id="gen" datetime="__GENERATED__">__GENERATED__</time>. Click a team row to see its players. Big number = points from
    the day; small number under a team's points = points left on the bench (BE and IR). Week column:
    counted / benched, with the combined total underneath.</p>
</main>

<dialog id="detail">
  <button class="close" id="detail-close">Close</button>
  <h2 id="detail-title"></h2>
  <p class="muted" id="detail-sub"></p>
  <div id="detail-content"></div>
</dialog>

<script type="application/json" id="data">__DATA__</script>
<script>
const WEEKS = JSON.parse(document.getElementById('data').textContent); // newest first
const BENCH = new Set([7, 8]);                         // BE and IR
const ABBR = { G: 'G', A: 'A', PPP: 'PPP', SHP: 'SHP', SOG: 'SOG', HIT: 'H', BLK: 'B',
               W: 'W', GA: 'GA', SV: 'SV', SO: 'SO', OTL: 'OTL' };
const NOT_IN_CELL = new Set(['SA', 'SV%']);           // shown in the popover only
const INJ_TAG = { OUT: 'O', DAY_TO_DAY: 'DTD' };
const STATE_TEXT = {
  played: 'Played',
  dnp: "Team played, player didn't",
  nogame: 'Team had no game',
  pending: 'Day not finished yet',
};

// Tiny DOM helper. Using textContent/append (never innerHTML) because team and player
// names come from ESPN.
function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) e.append(kid);
  return e;
}
const fmt = (n) => (Math.round(n * 10) / 10).toFixed(1);
const dayLabel = (d) => new Date(d + 'T12:00:00')
  .toLocaleDateString(undefined, { weekday: 'short', month: 'numeric', day: 'numeric' });
const sum = (xs, f) => xs.reduce((t, x) => t + f(x), 0);
const compact = (p) => Object.entries(p.stats)
  .filter(([k]) => !NOT_IN_CELL.has(k)).map(([k, v]) => `${v}${ABBR[k] || k}`).join(' ');

function openPlayer(r, date, p) {
  const rows = [
    ['Slot', `${p.slot}${BENCH.has(p.slot_id) ? (p.slot_id === 8 ? ' (IR, not counted)' : ' (bench, not counted)') : ' (active)'}`],
    ['Points', p.state === 'played' ? fmt(p.points) : '–'],
    ['Day', STATE_TEXT[p.state] || p.state],
  ];
  if (p.state === 'dnp') rows.push(['Status when pulled', p.injury || 'unknown']);
  if (p.state === 'pending') rows.push(['Injury status (last update)', p.injury || 'unknown']);
  for (const [k, v] of Object.entries(p.stats)) rows.push([k, String(v)]);
  document.getElementById('detail-title').textContent = `${r.name} (${r.pos}), ${dayLabel(date)}`;
  document.getElementById('detail-sub').textContent = '';
  document.getElementById('detail-content').replaceChildren(
    h('table', {}, h('tbody', {}, rows.map(([a, b]) =>
      h('tr', {}, h('td', { style: 'color:var(--muted)' }, a), h('td', { style: 'text-align:left' }, b))))));
  document.getElementById('detail').showModal();
}

// Week column, same format for teams and players: "counted / benched" over an italic "= total".
function weekCell(counted, benched) {
  return h('td', { class: 'total' },
    h('span', {}, fmt(counted), ' / ', h('span', { class: 'bn' + (benched === 0 ? ' zero' : '') }, benched === 0 ? '–' : fmt(benched))),
    h('small', { class: 'tt' }, `= ${fmt(counted + benched)}`));
}

function playerCell(date, r, p, maxP) {
  if (!p) return h('td', { class: 'absent', title: 'Not on this roster' });
  const ir = p.slot_id === 8, be = p.slot_id === 7;
  const cls = ['cell', 'pc'];
  if (ir) cls.push('ir');
  let main, tag = null;
  if (p.state === 'played') {
    main = fmt(p.points);
    // Colour is the only slot cue: amber = bench/IR (not counted), red = negative in an active slot.
    if (ir || be) cls.push('ben'); else if (p.points < 0) cls.push('down'); else if (p.points === 0) cls.push('quiet');
  } else if (p.state === 'dnp') {
    main = fmt(0); cls.push('quiet');
    // DNP is true whatever the player's status. The injury field is only a snapshot from when the
    // day was pulled, so for finished days it goes in the popover, not the cell. Active slots only:
    // that's where it means a wasted spot.
    if (!ir && !be) tag = 'DNP';
  } else {
    main = p.state === 'pending' ? '…' : '–'; cls.push('quiet');
    // Today, before games: the injury status is current (as of the last update), so show it.
    if (p.state === 'pending' && !ir && !be) tag = INJ_TAG[p.injury] || null;
  }
  const btn = h('button', { class: cls.join(' '), title: `${r.name}, ${dayLabel(date)}: ${p.slot}${compact(p) ? ' - ' + compact(p) : ''}`,
      onclick: () => openPlayer(r, date, p) },
    h('span', { class: 'top' }, h('span', { class: 'pt' }, main),
      (ir || be) && h('span', { class: 'tag' }, ir ? 'IR' : 'BE'),
      tag && h('span', { class: 'tag dnp', title: p.state === 'pending' ? 'Injury status as of the last update' : "Team played, player didn't" }, tag)),
    p.state === 'played' && compact(p) && h('span', { class: 'sl' }, compact(p)));
  return h('td', {}, btn);
}

// Every player who was on this team at any point in the week, one row each, best scorer first.
function playerRows(m, x, sps, maxP) {
  const byId = new Map();
  for (const sp of sps) for (const p of m.days[sp][x.s].players) {
    const key = p.id ?? p.player;
    if (!byId.has(key)) byId.set(key, { name: p.player, pos: p.pos || '', days: {} });
    byId.get(key).days[sp] = p;
  }
  const rows = [...byId.values()].map((r) => {
    const ps = Object.values(r.days);
    r.total = sum(ps, (p) => p.points);
    r.counted = sum(ps.filter((p) => !BENCH.has(p.slot_id)), (p) => p.points);
    r.benched = sum(ps.filter((p) => BENCH.has(p.slot_id)), (p) => p.points);
    return r;
  }).sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

  return rows.map((r) => {
    // Joined/left notes only look at days that have happened (future days have no rosters).
    const live = sps.filter((sp) => !m.days[sp].future);
    const idx = live.map((sp) => (r.days[sp] ? 1 : 0));
    const first = idx.indexOf(1), last = idx.lastIndexOf(1);
    const notes = [];
    const wd = (sp) => new Date(m.days[sp].date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short' });
    // "+ Tue" = first day on the roster; "- Tue" = first day gone from it.
    if (first > 0) notes.push(h('span', { class: 'add', title: 'Joined the roster' }, `+ ${wd(live[first])}`));
    if (last < live.length - 1) notes.push(h('span', { class: 'drop', title: 'Left the roster' }, `− ${wd(live[last + 1])}`));
    return h('tr', { class: 'prow' },
      h('td', {}, h('span', { class: 'pname' }, r.name), h('span', { class: 'ppos' }, r.pos),
        notes.length > 0 && h('span', { class: 'note' }, notes)),
      sps.map((sp) => m.days[sp].future
        ? h('td', { class: 'future' }, '·')
        : playerCell(m.days[sp].date, r, r.days[sp], maxP)),
      weekCell(r.counted, r.benched));
  });
}

// One <tbody> per team: the team's summary row, then (when open) its player rows underneath.
// The player rows are only built the first time the team is opened.
function teamBody(m, x, sps, maxP, maxAbs, isTop) {
  const tb = h('tbody', { class: 'team' });
  const toggle = h('button', { class: 'tg', 'aria-expanded': 'false' },
    h('span', { class: 'chev' }),
    h('span', isTop ? { class: 'winner', title: 'Higher total this week' } : {}, x.name));
  const row = h('tr', { class: 'teamrow' },
    h('td', {}, toggle),
    sps.map((sp) => {
      const d = m.days[sp];
      if (d.future) return h('td', { class: 'future' }, '·');
      const side = d[x.s], v = side.active_pts;
      const c = h('span', { class: 'cell ' + (v > 0 ? 'pos' : v < 0 ? 'neg' : '') },
        fmt(v), h('small', { class: side.bench_pts > 0 ? 'left' : '' }, `bench ${fmt(side.bench_pts)}`));
      c.style.setProperty('--a', (Math.min(Math.abs(v) / maxAbs, 1) * 0.6).toFixed(2));
      return h('td', {}, c);
    }),
    weekCell(x.active, x.bench));
  tb.append(row);

  let built = false;
  tb.isOpen = () => tb.classList.contains('open');
  tb.setOpen = (open) => {
    if (open && !built) { built = true; tb.append(...playerRows(m, x, sps, maxP)); }
    tb.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    tb.dispatchEvent(new Event('rowtoggle'));
  };
  row.addEventListener('click', () => tb.setOpen(!tb.isOpen()));  // the button's click bubbles up to here
  return tb;
}

// Season-to-date bench/active points per team, counting every saved week up to and including `upTo`.
function seasonTotals(upTo) {
  const t = {};
  for (const wk of WEEKS) {
    if (wk.week > upTo) continue;
    for (const m of [...wk.matchups, ...(wk.byes || [])]) for (const s of (m.away == null ? ['home'] : ['home', 'away'])) {
      const e = (t[m[s]] ||= { bench: 0, active: 0 });
      for (const d of Object.values(m.days)) { e.bench += d[s].bench_pts; e.active += d[s].active_pts; }
    }
  }
  return t;
}

// The "This week / Season" control used in the header of both cards at the top. Each card keeps its
// own choice (`current` and `choose`), so they look and work the same but don't affect each other.
function scopeToggle(current, choose) {
  return h('div', { class: 'seg', role: 'group', 'aria-label': 'Time span' },
    [['week', 'This week'], ['season', 'Season']].map(([k, label]) => h('button', {
      'aria-pressed': String(current === k), onclick: () => choose(k) }, label)));
}

// Compact leaderboard of bench vs. active points for this week or the season so far. Click a column
// header to sort by it (click again to flip); the rank column follows the current order. The span and
// the sort stick across weeks.
let benchScope = 'week';
let benchSort = { key: 'bench', dir: 'desc' };   // 'bench' or 'active', whichever span is showing
function benchCard(rows, w) {
  const season = seasonTotals(w.week);
  for (const x of rows) {
    x.sbench = season[x.id]?.bench ?? 0;
    x.sactive = season[x.id]?.active ?? 0;
  }
  const card = h('section', { class: 'card bench-card' });
  const num = (v, bench) => h('td', { class: 'num' + (bench ? ' bn' : '') }, fmt(v));
  const draw = () => {
    const pre = benchScope === 'season' ? 's' : '';
    const sign = benchSort.dir === 'desc' ? -1 : 1;
    const sorted = [...rows].sort((a, b) =>
      sign * (a[pre + benchSort.key] - b[pre + benchSort.key]) || a.name.localeCompare(b.name));
    const th = (key, label) => h('th', {
      class: 'sortable' + (benchSort.key === key ? ` sorted ${benchSort.dir}` : ''),
      'aria-sort': benchSort.key === key ? (benchSort.dir === 'desc' ? 'descending' : 'ascending') : 'none',
    }, h('button', { class: 'sort', title: 'Sort by ' + label, onclick: () => {
      benchSort = benchSort.key === key ? { key, dir: benchSort.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' };
      draw();
    } }, label));
    card.replaceChildren(
      h('div', { class: 'card-head' }, h('h2', {}, 'Points left on the bench'),
        scopeToggle(benchScope, (k) => { benchScope = k; draw(); })),
      h('table', { class: 'bench' },
        h('thead', {}, h('tr', {}, h('th', {}, '#'), h('th', {}, 'Team'), th('bench', 'Bench'), th('active', 'Active'))),
        h('tbody', {}, sorted.map((x, i) => h('tr', {},
          h('td', {}, String(i + 1)),
          h('td', {}, x.bye ? `${x.name} (bye)` : x.name),
          num(x[pre + 'bench'], true), num(x[pre + 'active']))))));
  };
  draw();
  return card;
}

// The best individual scores from players sitting in a BE or IR slot, i.e. points that didn't count,
// for this week or the season so far. Click a row for the player's day. The span sticks across weeks.
let missesScope = 'week';
function missesCard(w) {
  const card = h('section', { class: 'card misses-card' });
  const draw = () => {
    const weeks = missesScope === 'week' ? [w] : WEEKS.filter((wk) => wk.week <= w.week);
    const rows = [];
    for (const wk of weeks) for (const m of [...wk.matchups, ...(wk.byes || [])]) {
      for (const s of (m.away == null ? ['home'] : ['home', 'away'])) for (const d of Object.values(m.days)) {
        if (d.future) continue;
        for (const p of d[s].players) {
          if (BENCH.has(p.slot_id) && p.state === 'played' && p.points > 0) rows.push({ p, date: d.date, team: wk.teams[m[s]] });
        }
      }
    }
    rows.sort((a, b) => b.p.points - a.p.points || a.p.player.localeCompare(b.p.player));
    const body = rows.slice(0, 8).map(({ p, date, team }) => h('tr', {
        class: 'miss', title: 'Click for details',
        onclick: () => openPlayer({ name: p.player, pos: p.pos }, date, p) },
      h('td', { class: 'pt' }, fmt(p.points)),
      h('td', { class: 'who' }, p.player, ' ', h('span', { class: 'ppos' }, p.pos),
        p.slot_id === 8 && h('span', { class: 'tag' }, 'IR')),   // every row is a bench slot; only IR is worth marking
      h('td', { class: 'team' }, team),
      h('td', { class: 'day' }, dayLabel(date))));
    card.replaceChildren(
      h('div', { class: 'card-head' }, h('h2', {}, 'Biggest bench misses'),
        scopeToggle(missesScope, (k) => { missesScope = k; draw(); })),
      rows.length
        ? h('table', { class: 'misses' }, h('tbody', {}, body))
        : h('p', { class: 'muted' }, 'No points scored from the bench yet.'));
  };
  draw();
  return card;
}

function renderWeek(w) {
  const root = document.getElementById('week');
  const first = w.matchups[0];
  const sps = Object.keys(first.days).map(Number).sort((a, b) => a - b);
  const dates = sps.map((sp) => first.days[sp].date);
  document.getElementById('week-range').textContent =
    `${dayLabel(dates[0])} to ${dayLabel(dates[dates.length - 1])}`;

  // Heat scales: the biggest single swing this week maps to full colour (separately for team days
  // and for individual players).
  const byes = w.byes || [];                    // the team with no opponent this week (home side only)
  const sidesOf = (m) => (m.away == null ? ['home'] : ['home', 'away']);
  let maxAbs = 1, maxP = 1;
  for (const m of [...w.matchups, ...byes]) for (const d of Object.values(m.days)) for (const s of sidesOf(m)) {
    maxAbs = Math.max(maxAbs, Math.abs(d[s].active_pts));
    for (const p of d[s].players) maxP = Math.max(maxP, Math.abs(p.points));
  }

  const bench = [];
  const card = (m) => {
    const bye = m.away == null;
    const days = sps.map((sp) => m.days[sp]);
    const sides = sidesOf(m).map((s) => ({
      s, bye, id: m[s], name: w.teams[m[s]],
      active: sum(days, (d) => d[s].active_pts), bench: sum(days, (d) => d[s].bench_pts),
    }));
    for (const x of sides) bench.push(x);
    const top = Math.max(...sides.map((x) => x.active));

    const head = h('tr', {}, h('th', {}, ''),
      sps.map((sp) => {
        const d = m.days[sp];
        return h('th', { class: d.future ? 'future' : d.today ? 'today' : '' }, dayLabel(d.date));
      }), h('th', {}, 'Week'));
    const bodies = sides.map((x) => teamBody(m, x, sps, maxP, maxAbs, !bye && x.active === top && x.active > 0));

    let both = null;                            // nothing to pair up on a bye
    if (!bye) {
      both = h('button', { class: 'btn' }, 'Open both teams');
      both.addEventListener('click', () => {
        const open = !bodies.every((b) => b.isOpen());
        bodies.forEach((b) => b.setOpen(open));
      });
      const sync = () => { both.textContent = bodies.every((b) => b.isOpen()) ? 'Close both teams' : 'Open both teams'; };
      bodies.forEach((b) => b.addEventListener('rowtoggle', sync));
    }

    return h('section', { class: 'card' },
      h('div', { class: 'card-head' },
        h('h2', {}, bye ? `Bye week: ${sides[0].name}` : `${sides[0].name} vs ${sides[1].name}`), both),
      h('div', { class: 'scroll' },
        h('table', { class: 'ov' },
          h('colgroup', {}, h('col', { class: 'name' }), sps.map(() => h('col')), h('col', { class: 'tot' })),
          h('thead', {}, head), bodies)));
  };
  const cards = w.matchups.map(card);
  const byeCards = byes.map(card);              // after the matchups, at the bottom

  root.replaceChildren(h('div', { class: 'top-grid' }, benchCard(bench, w), missesCard(w)), ...cards, ...byeCards);
  document.getElementById('toggle-all').textContent = 'Expand all teams';
}

const select = document.getElementById('week-select');
const prevBtn = document.getElementById('week-prev'), nextBtn = document.getElementById('week-next');
WEEKS.forEach((w, i) => select.append(h('option', { value: i }, `Week ${w.week}`)));
function showWeek(i) {                          // WEEKS is newest first, so "previous week" is i + 1
  select.value = String(i);
  prevBtn.disabled = i >= WEEKS.length - 1;
  nextBtn.disabled = i <= 0;
  renderWeek(WEEKS[i]);
  try { history.replaceState(null, '', '#week-' + WEEKS[i].week); } catch (e) { /* e.g. some file:// setups */ }
}
select.addEventListener('change', () => showWeek(Number(select.value)));
prevBtn.addEventListener('click', () => showWeek(Number(select.value) + 1));
nextBtn.addEventListener('click', () => showWeek(Number(select.value) - 1));
document.getElementById('toggle-all').addEventListener('click', (e) => {
  const all = [...document.querySelectorAll('tbody.team')];
  const open = !all.every((b) => b.isOpen());
  all.forEach((b) => b.setOpen(open));
  e.target.textContent = open ? 'Collapse all teams' : 'Expand all teams';
});
const gen = document.getElementById('gen');  // show the build time in the viewer's own timezone
if (!isNaN(new Date(gen.getAttribute('datetime')))) gen.textContent = new Date(gen.getAttribute('datetime')).toLocaleString();
const dlg = document.getElementById('detail');
document.getElementById('detail-close').addEventListener('click', () => dlg.close());
dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });  // click on backdrop
if (WEEKS.length) {
  const wanted = (location.hash.match(/week-(\d+)/) || [])[1];   // a link like ...#week-2 opens that week
  const start = WEEKS.findIndex((w) => String(w.week) === wanted);
  showWeek(start >= 0 ? start : 0);
} else {
  document.getElementById('week').textContent = 'No week_N.json files found.';
}
</script>
</body>
</html>
"""


def main():
    weeks = [json.loads(p.read_text(encoding="utf-8")) for p in DATA.glob("week_*.json")]
    weeks.sort(key=lambda w: w["week"], reverse=True)  # newest first
    # "</" inside JSON could end the <script> tag early, so escape it.
    data = json.dumps(weeks).replace("</", "<\\/")
    html = PAGE.replace("__LEAGUE__", LEAGUE_NAME).replace("__DATA__", data).replace(
        "__GENERATED__", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {SITE / 'index.html'} ({len(weeks)} week(s))")


if __name__ == "__main__":
    main()
