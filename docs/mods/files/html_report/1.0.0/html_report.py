"""HTML レポート

この MOD が貯めた記録から、作業時間のグラフとアプリ別ランキングが入った HTML レポートを作ってブラウザで開きます。
保存先: ドキュメント\\WorkMonitorレポート\\report.html
"""

import html
import os
from datetime import date, timedelta

MOD_INFO = {
    "name": "HTML レポート",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "直近30日の作業時間グラフとアプリ別ランキングの HTML レポートを作り、ブラウザで開きます。",
    "api": 2,   # api.open_path を使う（WorkMonitor 1.7.0 以降）
}

OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "WorkMonitorレポート")

TEMPLATE = """<!doctype html><html lang="ja"><meta charset="utf-8"><title>作業レポート</title>
<style>
body{{font-family:"Segoe UI","Yu Gothic UI",sans-serif;max-width:860px;margin:32px auto;padding:0 16px;color:#1d2330;background:#f6f7fb}}
@media (prefers-color-scheme:dark){{body{{color:#e8eaf0;background:#161922}}.card{{background:#20242f!important}}}}
h1{{font-size:24px}} .card{{background:#fff;border-radius:12px;padding:16px 20px;margin:16px 0}}
.bars{{display:flex;align-items:flex-end;gap:3px;height:160px}}
.bar{{flex:1;background:#4f6bed;border-radius:3px 3px 0 0;min-height:1px;position:relative}}
.bar.ok{{background:#22a06b}} .bar:hover::after{{content:attr(data-t);position:absolute;bottom:100%;left:50%;
transform:translateX(-50%);font-size:11px;white-space:nowrap;background:#000;color:#fff;padding:2px 6px;border-radius:4px}}
table{{border-collapse:collapse;width:100%}} td{{padding:6px 4px;border-bottom:1px solid #8883}}
.big{{font-size:28px;font-weight:bold}} .sub{{color:#888;font-size:13px}}
</style>
<h1>📊 作業レポート</h1><p class="sub">{start} 〜 {end}（作成 {today}）</p>
<div class="card"><div class="big">{total}</div><div class="sub">合計 · 1日平均 {avg} · 作業した日 {days} 日</div></div>
<div class="card"><h3>日別の作業時間</h3><div class="bars">{bars}</div></div>
<div class="card"><h3>アプリ別ランキング</h3><table>{rows}</table></div>
</html>"""


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分"


def setup(api):
    api.data.setdefault("days", {})       # 日付 → {"sec", "goal", "apps"}
    s = {"n": 0}

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = {"sec": status["today_sec"], "goal": status["goal_min"] * 60,
                                                     "apps": dict(status["today_by_app"])}
        s["n"] += 1
        if s["n"] % 120 == 0:
            old = (date.today() - timedelta(days=90)).isoformat()
            api.data["days"] = {k: v for k, v in api.data["days"].items() if k >= old}
            api.save_data()

    def make():
        days = [date.today() - timedelta(days=29 - i) for i in range(30)]
        recs = [api.data["days"].get(d.isoformat(), {"sec": 0, "goal": 0, "apps": {}}) for d in days]
        top = max([r["sec"] for r in recs] + [1])
        bars, apps = [], {}
        for d, r in zip(days, recs):
            ok = " ok" if r["goal"] and r["sec"] >= r["goal"] else ""
            bars.append(f'<div class="bar{ok}" style="height:{r["sec"] * 100 / top:.1f}%" '
                        f'data-t="{d:%m/%d} {fmt(r["sec"])}"></div>')
            for k, v in r["apps"].items():
                apps[k] = apps.get(k, 0) + v
        total = sum(r["sec"] for r in recs)
        worked = sum(1 for r in recs if r["sec"] >= 60)
        rows = "".join(f"<tr><td>{i + 1}</td><td>{html.escape(k)}</td><td>{fmt(v)}</td></tr>"
                       for i, (k, v) in enumerate(sorted(apps.items(), key=lambda kv: -kv[1])[:15]))
        page = TEMPLATE.format(start=days[0], end=days[-1], today=date.today(), total=fmt(total),
                               avg=fmt(total / max(worked, 1)), days=worked, bars="".join(bars),
                               rows=rows or "<tr><td>まだデータがありません</td></tr>")
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "report.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        api.save_data()
        api.open_path(path)

    api.add_action("レポートを作って開く", make)


def teardown(api):
    api.save_data()
