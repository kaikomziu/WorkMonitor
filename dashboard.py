"""作業記録から表・グラフのダッシュボード（HTML）を作ってブラウザで開く"""

import csv
import glob
import json
import os

import core

MAX_DAYS = 90  # 埋め込む日数（古い分は省略）


def load_logs(config):
    """日付 → [[開始, 秒, 表示名, タイトル, カテゴリ], ...]（作業に数えないアプリは除く）

    表示名・カテゴリは今の設定で引き直すので、設定を変えると過去の記録にも反映される。
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
                    rows.append([r["start"], int(float(r["seconds"])), info["name"], r["title"], info["category"]])
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
  :root { --bg:#f6f7f9; --card:#fff; --text:#1d2330; --sub:#6b7280; --line:#e5e7eb; --accent:#4f6bed; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14161b; --card:#1d2027; --text:#e8eaf0; --sub:#9aa1ad; --line:#2c3039; --accent:#7b93ff; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font-family:"Segoe UI","Yu Gothic UI",sans-serif; }
  main { max-width:1100px; margin:0 auto; padding:24px 16px 48px; }
  header { display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:16px; }
  h1 { font-size:20px; margin:0; }
  select { font:inherit; padding:6px 10px; border-radius:8px; border:1px solid var(--line); background:var(--card); color:var(--text); }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; min-width:0; }
  .kpi .label { color:var(--sub); font-size:13px; }
  .kpi .value { font-size:26px; font-weight:600; margin-top:4px; font-variant-numeric:tabular-nums; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px; }
  @media (max-width:760px) { .grid { grid-template-columns:1fr; } }
  h2 { font-size:15px; margin:0 0 12px; }
  .chart { position:relative; height:260px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th, td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }
  th { color:var(--sub); font-weight:500; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
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
    <label>日付 <select id="date"></select></label>
  </header>
  <div id="root"></div>
</main>
<script>
const DATA = __DATA__;
const dates = Object.keys(DATA).sort();
const root = document.getElementById('root');
const sel = document.getElementById('date');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PALETTE = ['#4f6bed','#22a06b','#e2a03f','#d9534f','#8e6bd8','#2bb3c0','#e57fb0','#7f8c8d'];
const fmt = s => `${Math.floor(s/3600)}時間${String(Math.floor(s%3600/60)).padStart(2,'0')}分`;
const total = d => (DATA[d]||[]).reduce((a,r)=>a+r[1],0);
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// カテゴリの色はアプリ本体と共通
const COLORS = __COLORS__;
const catTotals = {};
dates.forEach(d => DATA[d].forEach(r => catTotals[r[4]] = (catTotals[r[4]]||0) + r[1]));
const CATS = Object.keys(catTotals).sort((a,b)=>catTotals[b]-catTotals[a]);
const catColor = c => COLORS[c] || PALETTE[CATS.indexOf(c) % PALETTE.length];
let charts = [];

if (!dates.length) {
  root.innerHTML = '<div class="card empty">まだ記録がありません。WorkMonitor を起動して作業してください。</div>';
} else {
  dates.slice().reverse().forEach(d => sel.add(new Option(d, d)));
  sel.onchange = () => render(sel.value);
  render(dates[dates.length-1]);
}

function sumBy(rows, idx) {
  const m = {};
  rows.forEach(r => m[r[idx]] = (m[r[idx]]||0) + r[1]);
  return Object.entries(m).sort((a,b)=>b[1]-a[1]);
}

function render(day) {
  charts.forEach(c => c.destroy()); charts = [];
  const rows = DATA[day] || [];
  const dayTotal = total(day) || 1;

  // 直近7日（選択日を含む）の平均
  const idx = dates.indexOf(day);
  const last7 = dates.slice(Math.max(0, idx-6), idx+1);
  const avg7 = last7.reduce((a,d)=>a+total(d),0) / last7.length;

  const cats = sumBy(rows, 4);
  const appCat = {};
  rows.forEach(r => appCat[r[2]] = r[4]);
  const apps = sumBy(rows, 2);
  const byTitle = {};
  rows.forEach(r => { const k = r[2] + '\u0000' + r[3]; byTitle[k] = (byTitle[k]||0) + r[1]; });
  const titles = Object.entries(byTitle).sort((a,b)=>b[1]-a[1]).slice(0,15);
  const first = rows.length ? rows.map(r=>r[0]).sort()[0] : '-';

  root.innerHTML = `
    <div class="kpis">
      <div class="card kpi"><div class="label">この日の作業時間</div><div class="value">${fmt(total(day))}</div></div>
      <div class="card kpi"><div class="label">直近7日の平均</div><div class="value">${fmt(avg7)}</div></div>
      <div class="card kpi"><div class="label">いちばん多いカテゴリ</div><div class="value" style="font-size:20px">${cats[0] ? esc(cats[0][0]) : '-'}</div></div>
      <div class="card kpi"><div class="label">作業開始</div><div class="value">${first.slice(0,5)}</div></div>
    </div>
    <div class="card" style="margin-bottom:12px"><h2>日別の作業時間（直近30日・カテゴリ別）</h2><div class="chart"><canvas id="cDaily"></canvas></div></div>
    <div class="grid">
      <div class="card"><h2>カテゴリ別</h2><div class="chart"><canvas id="cCat"></canvas></div></div>
      <div class="card"><h2>時間帯別</h2><div class="chart"><canvas id="cHour"></canvas></div></div>
    </div>
    <div class="grid">
      <div class="card"><h2>カテゴリ別の内訳</h2>
        <table><thead><tr><th>カテゴリ</th><th style="width:35%"></th><th class="num">時間</th><th class="num">割合</th></tr></thead><tbody>
        ${cats.map(([c,s])=>`<tr><td><span class="dot" style="background:${catColor(c)}"></span>${esc(c)}</td><td><div class="bar" style="width:${s/cats[0][1]*100}%;background:${catColor(c)}"></div></td><td class="num">${fmt(s)}</td><td class="num">${(s/dayTotal*100).toFixed(1)}%</td></tr>`).join('')}
        </tbody></table></div>
      <div class="card"><h2>アプリ別の内訳</h2>
        <table><thead><tr><th>アプリ</th><th>カテゴリ</th><th class="num">時間</th><th class="num">割合</th></tr></thead><tbody>
        ${apps.map(([a,s])=>`<tr><td>${esc(a)}</td><td><span class="tag">${esc(appCat[a])}</span></td><td class="num">${fmt(s)}</td><td class="num">${(s/dayTotal*100).toFixed(1)}%</td></tr>`).join('')}
        </tbody></table></div>
    </div>
    <div class="card"><h2>ウィンドウ別 上位15件</h2>
      <table><thead><tr><th>アプリ</th><th>ウィンドウ</th><th class="num">時間</th></tr></thead><tbody>
      ${titles.map(([k,s])=>{const [a,t]=k.split('\u0000');return `<tr><td>${esc(a)}</td><td class="title" title="${esc(t)}">${esc(t)||'-'}</td><td class="num">${fmt(s)}</td></tr>`}).join('')}
      </tbody></table></div>`;

  Chart.defaults.color = css('--sub');
  Chart.defaults.borderColor = css('--line');
  Chart.defaults.font.family = '"Segoe UI","Yu Gothic UI",sans-serif';
  const legend = { display:true, position:'bottom', labels:{ boxWidth:10, boxHeight:10 } };
  const opt = { responsive:true, maintainAspectRatio:false, plugins:{ legend:{display:false} } };

  // 日別（カテゴリで積み上げ）
  const d30 = dates.slice(Math.max(0, idx-29), idx+1);
  const catOfDay = (d, c) => DATA[d].filter(r=>r[4]===c).reduce((a,r)=>a+r[1],0);
  charts.push(new Chart(document.getElementById('cDaily'), {
    type:'bar',
    data:{ labels:d30.map(d=>d.slice(5)), datasets:CATS.map(c=>({ label:c, data:d30.map(d=>+(catOfDay(d,c)/3600).toFixed(2)),
      backgroundColor:catColor(c), borderRadius:3 })) },
    options:{ ...opt, scales:{ x:{stacked:true}, y:{ stacked:true, title:{display:true,text:'時間'} } },
      plugins:{ legend, tooltip:{ callbacks:{ label:c=>`${c.dataset.label}: ${fmt(catOfDay(d30[c.dataIndex], c.dataset.label))}`,
        footer:items=>`合計 ${fmt(total(d30[items[0].dataIndex]))}` } } },
      onClick:(e,els)=>{ if(els.length){ sel.value=d30[els[0].index]; render(sel.value); } } }
  }));

  charts.push(new Chart(document.getElementById('cCat'), {
    type:'doughnut',
    data:{ labels:cats.map(x=>x[0]), datasets:[{ data:cats.map(x=>x[1]), backgroundColor:cats.map(x=>catColor(x[0])), borderColor:css('--card'), borderWidth:2 }]},
    options:{ ...opt, plugins:{ legend:{...legend, position:'right'}, tooltip:{ callbacks:{ label:c=>`${c.label}: ${fmt(c.raw)}` } } } }
  }));

  // 時間帯別（カテゴリで積み上げ）
  const hourCat = (h, c) => rows.filter(r=>parseInt(r[0].slice(0,2))===h && r[4]===c).reduce((a,r)=>a+r[1],0);
  charts.push(new Chart(document.getElementById('cHour'), {
    type:'bar',
    data:{ labels:[...Array(24).keys()].map(h=>h+'時'), datasets:cats.map(([c])=>({ label:c, data:[...Array(24).keys()].map(h=>Math.round(hourCat(h,c)/60)), backgroundColor:catColor(c), borderRadius:2 })) },
    options:{ ...opt, scales:{ x:{stacked:true}, y:{ stacked:true, max:60, title:{display:true,text:'分'} } } }
  }));
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
    html = HTML.replace("__DATA__", js(load_logs(config))).replace("__COLORS__", js(core.category_colors(config)))
    os.makedirs(core.DATA_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    if open_browser:
        os.startfile(out_path)  # 既定のブラウザで開く
    return out_path
