"""作業記録から表・グラフのダッシュボード（HTML）を作ってブラウザで開く"""

import csv
import glob
import json
import os

import core

MAX_DAYS = 400  # 埋め込む日数（月・前月比較に足りる分。古い分は省略）


def load_logs(config):
    """日付 → [[開始, 秒, 表示名, サイト・ウィンドウ名, カテゴリ], ...]（作業に数えないアプリは除く）

    表示名・カテゴリは今の設定で引き直すので、設定を変えると過去の記録にも反映される。
    ブラウザはページのタイトルではなくサイト名でまとめる（core.window_label）。
    """
    data = {}
    files = sorted(glob.glob(os.path.join(core.LOG_DIR, "????-??-??.csv")))[-MAX_DAYS:]
    for path in files:
        date = os.path.splitext(os.path.basename(path))[0]
        rows = []
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                info = core.app_info(config, r["app"])
                if info["count"]:
                    rows.append([r["start"], int(float(r["seconds"])), info["name"],
                                 core.window_label(r["app"], r["title"]), info["category"]])
        data[date] = rows
    return data


HTML = r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>作業時間ダッシュボード</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root { --bg:#f6f7f9; --card:#fff; --text:#1d2330; --sub:#6b7280; --line:#e5e7eb; --accent:#4f6bed; --up:#22a06b; --down:#d9534f; }
  :root[data-theme="dark"] { --bg:#14161b; --card:#1d2027; --text:#e8eaf0; --sub:#9aa1ad; --line:#2c3039; --accent:#7b93ff; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --bg:#14161b; --card:#1d2027; --text:#e8eaf0; --sub:#9aa1ad; --line:#2c3039; --accent:#7b93ff; }
  }
  .theme-btn { font:inherit; border:1px solid var(--line); background:var(--card); color:var(--text); border-radius:8px; padding:6px 12px; cursor:pointer; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font-family:"Segoe UI","Yu Gothic UI",sans-serif; }
  main { max-width:1100px; margin:0 auto; padding:24px 16px 48px; }
  header { display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:16px; }
  h1 { font-size:20px; margin:0; }
  .controls { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
  .seg { display:inline-flex; background:var(--card); border:1px solid var(--line); border-radius:10px; padding:3px; }
  .seg button { font:inherit; border:0; background:none; color:var(--sub); padding:5px 16px; border-radius:7px; cursor:pointer; }
  .seg button.on { background:var(--accent); color:#fff; }
  select { font:inherit; padding:6px 10px; border-radius:8px; border:1px solid var(--line); background:var(--card); color:var(--text); }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; min-width:0; overflow-x:auto; }
  .kpi .label { color:var(--sub); font-size:13px; }
  .kpi .value { font-size:26px; font-weight:600; margin-top:4px; font-variant-numeric:tabular-nums; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .kpi .note { color:var(--sub); font-size:12px; margin-top:2px; }
  .up { color:var(--up); } .down { color:var(--down); }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px; }
  @media (max-width:760px) { .grid { grid-template-columns:1fr; } }
  h2 { font-size:15px; margin:0 0 12px; }
  .chart { position:relative; height:260px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th, td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }
  th { color:var(--sub); font-weight:500; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
  td.title { max-width:420px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .bar { height:6px; border-radius:3px; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle; }
  .tag { font-size:12px; color:var(--sub); border:1px solid var(--line); border-radius:999px; padding:1px 8px; white-space:nowrap; }
  .empty { color:var(--sub); padding:40px; text-align:center; }
</style>
</head>
<body>
<main>
  <header>
    <h1>作業時間ダッシュボード</h1>
    <div class="controls">
      <div class="seg" id="group">
        <button data-group="app">アプリ別</button><button data-group="cat">カテゴリ別</button>
      </div>
      <div class="seg" id="mode">
        <button data-mode="day">日</button><button data-mode="week">週</button><button data-mode="month">月</button>
      </div>
      <select id="period"></select>
      <button class="theme-btn" id="theme"></button>
    </div>
  </header>
  <div id="root"></div>
</main>
<script>
const DATA = __DATA__;
const COLORS = __COLORS__;   // カテゴリの色はアプリ本体と共通
const GOAL = __GOAL__;       // 1日の目標（秒）。0 なら目標なし

// ---- テーマ（アプリの設定が初期値。ボタンで切り替え）----
const themeBtn = document.getElementById('theme');
const isDark = () => document.documentElement.dataset.theme === 'dark' ||
  (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
function setTheme(t) {
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
  else delete document.documentElement.dataset.theme;
  themeBtn.textContent = isDark() ? '☀ ライト' : '🌙 ダーク';
}
setTheme('__THEME__');
themeBtn.onclick = () => { setTheme(isDark() ? 'light' : 'dark'); if (sel.value) render(sel.value); };
const dates = Object.keys(DATA).sort();
const root = document.getElementById('root');
const sel = document.getElementById('period');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PALETTE = ['#4f6bed','#22a06b','#e2a03f','#d9534f','#8e6bd8','#2bb3c0','#e57fb0','#7f8c8d'];
const fmt = s => `${Math.floor(s/3600)}時間${String(Math.floor(s%3600/60)).padStart(2,'0')}分`;
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const total = d => (DATA[d]||[]).reduce((a,r)=>a+r[1],0);

// ---- 日付ユーティリティ ----
const pad = n => String(n).padStart(2,'0');
const iso = dt => `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}`;
const parse = s => { const [y,m,d] = s.split('-').map(Number); return new Date(y, m-1, d||1); };
const addDays = (s, n) => { const d = parse(s); d.setDate(d.getDate()+n); return iso(d); };
const mondayOf = s => { const d = parse(s); d.setDate(d.getDate() - (d.getDay()+6)%7); return iso(d); };
const monthOf = s => s.slice(0,7);
const md = s => `${+s.slice(5,7)}/${+s.slice(8,10)}`;
const WEEKDAY = ['日','月','火','水','木','金','土'];

const catTotals = {};
dates.forEach(d => DATA[d].forEach(r => catTotals[r[4]] = (catTotals[r[4]]||0) + r[1]));
const CATS = Object.keys(catTotals).sort((a,b)=>catTotals[b]-catTotals[a]);
const catColor = c => COLORS[c] || PALETTE[CATS.indexOf(c) % PALETTE.length];

// ---- まとめ方（アプリ別 / カテゴリ別）----
// アプリの色は全期間で多い順に固定（日付を切り替えても同じ色）
const appTotals = {};
dates.forEach(d => DATA[d].forEach(r => appTotals[r[2]] = (appTotals[r[2]]||0) + r[1]));
const APPS = Object.keys(appTotals).sort((a,b)=>appTotals[b]-appTotals[a]);
const OTHER = 'その他', OTHER_COLOR = '#8a919c', TOP_N = 7;   // グラフに出すのは上位7つ + その他
let group = 'app';
const GI = () => group === 'app' ? 2 : 4;            // 行の中の位置
const GN = () => group === 'app' ? 'アプリ' : 'カテゴリ';
const groupColor = k => k === OTHER ? OTHER_COLOR
  : group === 'app' ? PALETTE[APPS.indexOf(k) % (PALETTE.length - 1)] : catColor(k);
document.querySelectorAll('#group button').forEach(b => b.onclick = () => {
  group = b.dataset.group;
  document.querySelectorAll('#group button').forEach(x => x.classList.toggle('on', x.dataset.group === group));
  if (sel.value) render(sel.value);
});
document.querySelector('#group button[data-group="app"]').classList.add('on');

// ---- 期間（日・週・月）----
const MODES = {
  day:   { name:'日', prevName:'前日',   key:s=>s,          label:s=>`${s}（${WEEKDAY[parse(s).getDay()]}）`, days:k=>[k], prev:k=>addDays(k,-1) },
  week:  { name:'週', prevName:'前の週', key:mondayOf,      label:k=>`${md(k)}〜${md(addDays(k,6))} の週`,
           days:k=>[...Array(7).keys()].map(i=>addDays(k,i)), prev:k=>addDays(k,-7) },
  month: { name:'月', prevName:'前の月', key:monthOf,       label:k=>`${+k.slice(0,4)}年${+k.slice(5)}月`,
           days:k=>{ const d=parse(k+'-01'), out=[]; while(monthOf(iso(d))===k){ out.push(iso(d)); d.setDate(d.getDate()+1);} return out; },
           prev:k=>{ const d=parse(k+'-01'); d.setMonth(d.getMonth()-1); return monthOf(iso(d)); } },
};
let mode = 'day';
let charts = [];

document.querySelectorAll('#mode button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
sel.onchange = () => render(sel.value);

if (!dates.length) {
  root.innerHTML = '<div class="card empty">まだ記録がありません。WorkMonitor を起動して作業してください。</div>';
} else {
  // URL の末尾で最初の表示を選べる（例: dashboard.html#week）
  const h = location.hash.slice(1);
  setMode(MODES[h] ? h : 'day');
}

function setMode(m, key) {
  mode = m;
  document.querySelectorAll('#mode button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
  const keys = [...new Set(dates.map(MODES[m].key))].sort().reverse();
  sel.innerHTML = '';
  keys.forEach(k => sel.add(new Option(MODES[m].label(k), k)));
  if (key && keys.includes(key)) sel.value = key;
  render(sel.value);
}

function sumBy(rows, idx) {
  const m = {};
  rows.forEach(r => m[r[idx]] = (m[r[idx]]||0) + r[1]);
  return Object.entries(m).sort((a,b)=>b[1]-a[1]);
}

function diffHtml(now, before) {
  if (!before) return '<span class="note">比較なし</span>';
  const p = (now - before) / before * 100;
  return `<span class="${p >= 0 ? 'up' : 'down'}">${p >= 0 ? '▲' : '▼'} ${Math.abs(p).toFixed(0)}%</span>`;
}

function render(key) {
  charts.forEach(c => c.destroy()); charts = [];
  const M = MODES[mode];
  const days = M.days(key);
  const prevDays = M.days(M.prev(key));
  const rows = days.flatMap(d => DATA[d] || []);
  const sum = days.reduce((a,d)=>a+total(d),0);
  const prevSum = prevDays.reduce((a,d)=>a+total(d),0);
  const base = sum || 1;
  const cats = sumBy(rows, 4);
  const prevCats = Object.fromEntries(sumBy(prevDays.flatMap(d => DATA[d] || []), 4));
  const appCat = {};
  rows.forEach(r => appCat[r[2]] = r[4]);
  const apps = sumBy(rows, 2);
  const prevApps = Object.fromEntries(sumBy(prevDays.flatMap(d => DATA[d] || []), 2));
  const byTitle = {};
  rows.forEach(r => { const k = r[2] + '\u0000' + r[3]; byTitle[k] = (byTitle[k]||0) + r[1]; });
  const titles = Object.entries(byTitle).sort((a,b)=>b[1]-a[1]).slice(0,15);
  // グラフ用: 選んだまとめ方で集計（上位 TOP_N 以外は「その他」）
  const groups = sumBy(rows, GI());
  const prevGroups = Object.fromEntries(sumBy(prevDays.flatMap(d => DATA[d] || []), GI()));
  const topKeys = groups.slice(0, TOP_N).map(x => x[0]);
  const keyOf = r => topKeys.includes(r[GI()]) ? r[GI()] : OTHER;
  const chartGroups = sumBy(rows.map(r => { const c = r.slice(); c[GI()] = keyOf(r); return c; }), GI());

  // ---- 数字のカード ----
  let kpis;
  if (mode === 'day') {
    const idx = dates.indexOf(key);
    const last7 = dates.slice(Math.max(0, idx-6), idx+1);
    const avg7 = last7.reduce((a,d)=>a+total(d),0) / last7.length;
    const first = rows.length ? rows.map(r=>r[0]).sort()[0] : '-';
    kpis = [
      ['この日の作業時間', fmt(sum), GOAL ? (sum >= GOAL ? `<span class="up">🎉 目標達成（${Math.round(sum/GOAL*100)}%）</span>` : `目標の ${Math.round(sum/GOAL*100)}%`) : diffHtml(sum, prevSum) + ' 前日比'],
      ['直近7日の平均', fmt(avg7), ''],
      [`いちばん多い${GN()}`, groups[0] ? esc(groups[0][0]) : '-', groups[0] ? fmt(groups[0][1]) : ''],
      ['作業開始', first.slice(0,5), ''],
    ];
  } else {
    const worked = days.filter(d => total(d) > 0);
    const achieved = days.filter(d => GOAL && total(d) >= GOAL).length;
    kpis = [
      [`この${M.name}の合計`, fmt(sum), `${diffHtml(sum, prevSum)} ${M.prevName}（${fmt(prevSum)}）より`],
      ['1日の平均', fmt(worked.length ? sum / worked.length : 0), `作業した日 ${worked.length}日 / ${days.length}日`],
      [`いちばん多い${GN()}`, groups[0] ? esc(groups[0][0]) : '-', groups[0] ? fmt(groups[0][1]) : ''],
      GOAL ? ['目標を達成した日', `${achieved}日`, `目標 ${fmt(GOAL)} / 日`]
           : ['いちばん作業した日', worked.length ? md(worked.sort((a,b)=>total(b)-total(a))[0]) : '-', ''],
    ];
  }

  const trendTitle = mode === 'day' ? `日別の作業時間（直近30日・${GN()}別）` : `日別の作業時間（この${M.name}・${GN()}別）`;
  const third = mode === 'day'
    ? '<div class="card"><h2>時間帯別</h2><div class="chart"><canvas id="cHour"></canvas></div></div>'
    : `<div class="card"><h2>${GN()}別の推移（${M.prevName}と比べて）</h2><div class="chart"><canvas id="cCmp"></canvas></div></div>`;
  // 表は選んだまとめ方を先に出す
  const appTable = `<div class="card"><h2>アプリ別の内訳</h2>
        <table><thead><tr><th>アプリ</th><th>カテゴリ</th><th class="num">時間</th><th class="num">${mode === 'day' ? '割合' : M.prevName + '比'}</th></tr></thead><tbody>
        ${apps.slice(0,15).map(([a,s])=>`<tr><td><span class="dot" style="background:${group === 'app' ? groupColor(topKeys.includes(a) ? a : OTHER) : catColor(appCat[a])}"></span>${esc(a)}</td><td><span class="tag">${esc(appCat[a])}</span></td><td class="num">${fmt(s)}</td><td class="num">${mode === 'day' ? (s/base*100).toFixed(1)+'%' : diffHtml(s, prevApps[a])}</td></tr>`).join('')}
        </tbody></table></div>`;
  const catTable = `<div class="card"><h2>カテゴリ別の内訳</h2>
        <table><thead><tr><th>カテゴリ</th><th style="width:28%"></th><th class="num">時間</th><th class="num">${mode === 'day' ? '割合' : M.prevName + '比'}</th></tr></thead><tbody>
        ${cats.map(([c,s])=>`<tr><td><span class="dot" style="background:${catColor(c)}"></span>${esc(c)}</td><td><div class="bar" style="width:${s/cats[0][1]*100}%;background:${catColor(c)}"></div></td><td class="num">${fmt(s)}</td><td class="num">${mode === 'day' ? (s/base*100).toFixed(1)+'%' : diffHtml(s, prevCats[c])}</td></tr>`).join('')}
        </tbody></table></div>`;

  root.innerHTML = `
    <div class="kpis">${kpis.map(([l,v,n])=>`<div class="card kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="note">${n}</div></div>`).join('')}</div>
    <div class="card" style="margin-bottom:12px"><h2>${trendTitle}</h2><div class="chart"><canvas id="cDaily"></canvas></div></div>
    <div class="grid">
      <div class="card"><h2>${GN()}別</h2><div class="chart"><canvas id="cCat"></canvas></div></div>
      ${third}
    </div>
    <div class="grid">
      ${group === 'app' ? appTable + catTable : catTable + appTable}
    </div>
    <div class="card"><h2>サイト・ウィンドウ別 上位15件</h2>
      <table><thead><tr><th>アプリ</th><th>サイト・ウィンドウ</th><th class="num">時間</th></tr></thead><tbody>
      ${titles.map(([k,s])=>{const [a,t]=k.split('\u0000');return `<tr><td>${esc(a)}</td><td class="title" title="${esc(t)}">${esc(t)||'-'}</td><td class="num">${fmt(s)}</td></tr>`}).join('')}
      </tbody></table></div>`;

  Chart.defaults.color = css('--sub');
  Chart.defaults.borderColor = css('--line');
  Chart.defaults.font.family = '"Segoe UI","Yu Gothic UI",sans-serif';
  const legend = { display:true, position:'bottom', labels:{ boxWidth:10, boxHeight:10 } };
  const opt = { responsive:true, maintainAspectRatio:false, plugins:{ legend:{display:false} } };

  // ---- 日別（アプリ / カテゴリで積み上げ + 目標ライン）----
  let span;
  if (mode === 'day') {
    const idx = dates.indexOf(key);
    span = dates.slice(Math.max(0, idx-29), idx+1);
  } else {
    span = days;
  }
  // 表示する期間で多い順の上位 + その他
  const spanTop = sumBy(span.flatMap(d => DATA[d] || []), GI()).slice(0, TOP_N).map(x => x[0]);
  const spanKey = r => spanTop.includes(r[GI()]) ? r[GI()] : OTHER;
  const spanKeys = [...spanTop, ...(span.some(d => (DATA[d]||[]).some(r => spanKey(r) === OTHER)) ? [OTHER] : [])];
  const catOfDay = (d, c) => (DATA[d]||[]).filter(r=>spanKey(r)===c).reduce((a,r)=>a+r[1],0);
  const datasets = spanKeys.map(c => ({ label:c, data:span.map(d=>+(catOfDay(d,c)/3600).toFixed(2)),
    backgroundColor:groupColor(c), borderRadius:3, stack:'work' }));
  if (GOAL) datasets.push({ type:'line', label:'目標', data:span.map(()=>+(GOAL/3600).toFixed(2)), stack:'goal',
    borderColor:css('--sub'), borderDash:[6,4], borderWidth:1.5, pointRadius:0, fill:false });
  charts.push(new Chart(document.getElementById('cDaily'), {
    type:'bar',
    data:{ labels:span.map(d => mode === 'month' ? String(+d.slice(8)) : `${md(d)}(${WEEKDAY[parse(d).getDay()]})`), datasets },
    options:{ ...opt, scales:{ x:{stacked:true}, y:{ stacked:true, title:{display:true,text:'時間'} } },
      plugins:{ legend, tooltip:{ callbacks:{
        label:c => c.dataset.stack === 'goal' ? `目標: ${fmt(GOAL)}` : `${c.dataset.label}: ${fmt(catOfDay(span[c.dataIndex], c.dataset.label))}`,
        footer:items => `合計 ${fmt(total(span[items[0].dataIndex]))}` } } },
      onClick:(e,els)=>{ if(els.length) setMode('day', span[els[0].index]); } }
  }));

  charts.push(new Chart(document.getElementById('cCat'), {
    type:'doughnut',
    data:{ labels:chartGroups.map(x=>x[0]), datasets:[{ data:chartGroups.map(x=>x[1]), backgroundColor:chartGroups.map(x=>groupColor(x[0])), borderColor:css('--card'), borderWidth:2 }]},
    options:{ ...opt, plugins:{ legend:{...legend, position:'right'}, tooltip:{ callbacks:{ label:c=>`${c.label}: ${fmt(c.raw)}` } } } }
  }));

  if (mode === 'day') {
    // 時間帯別（アプリ / カテゴリで積み上げ）
    const hourCat = (h, c) => rows.filter(r=>parseInt(r[0].slice(0,2))===h && keyOf(r)===c).reduce((a,r)=>a+r[1],0);
    charts.push(new Chart(document.getElementById('cHour'), {
      type:'bar',
      data:{ labels:[...Array(24).keys()].map(h=>h+'時'), datasets:chartGroups.map(([c])=>({ label:c, data:[...Array(24).keys()].map(h=>Math.round(hourCat(h,c)/60)), backgroundColor:groupColor(c), borderRadius:2 })) },
      options:{ ...opt, scales:{ x:{stacked:true}, y:{ stacked:true, max:60, title:{display:true,text:'分'} } } }
    }));
  } else {
    // 前の期間との比較（多い順に最大10件）
    const names = [...new Set([...groups.map(x=>x[0]), ...Object.keys(prevGroups)])]
      .sort((a,b) => ((groups.find(x=>x[0]===b)||[0,0])[1] + (prevGroups[b]||0)) - ((groups.find(x=>x[0]===a)||[0,0])[1] + (prevGroups[a]||0)))
      .slice(0, 10);
    charts.push(new Chart(document.getElementById('cCmp'), {
      type:'bar',
      data:{ labels:names, datasets:[
        { label:M.prevName, data:names.map(c=>+((prevGroups[c]||0)/3600).toFixed(2)), backgroundColor:css('--line'), borderRadius:3 },
        { label:`この${M.name}`, data:names.map(c=>+((groups.find(x=>x[0]===c)||[0,0])[1]/3600).toFixed(2)), backgroundColor:names.map(c => groupColor(group === 'app' && !APPS.includes(c) ? OTHER : c)), borderRadius:3 },
      ]},
      options:{ ...opt, indexAxis:'y', scales:{ x:{ title:{display:true,text:'時間'} } },
        plugins:{ legend, tooltip:{ callbacks:{ label:c=>`${c.dataset.label}: ${fmt(c.raw*3600)}` } } } }
    }));
  }
}
</script>
</body>
</html>
"""


def build_dashboard(config=None, open_browser=True):
    config = config or core.load_config()
    out_path = os.path.join(core.DATA_DIR, "dashboard.html")

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    html = (HTML.replace("__DATA__", js(load_logs(config)))
                .replace("__COLORS__", js(core.category_colors(config)))
                .replace("__GOAL__", str(int(config.get("daily_goal_min", 0)) * 60))
                .replace("__THEME__", config.get("theme", "system")))
    os.makedirs(core.DATA_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    if open_browser:
        os.startfile(out_path)  # 既定のブラウザで開く
    return out_path
