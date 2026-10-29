"""CSV エクスポート

この MOD が貯めた日ごと・アプリごとの作業時間を CSV に書き出します。Excel で開けます。
"""

import csv
from datetime import date
from tkinter import filedialog

MOD_INFO = {
    "name": "CSV エクスポート",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "日ごと・アプリごとの作業時間（分）を CSV に書き出します。記録はこの MOD を入れた日からです。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("days", {})       # 日付 → {表示名: 秒}
    s = {"n": 0}

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = dict(status["today_by_app"])
        s["n"] += 1
        if s["n"] % 120 == 0:
            api.save_data()

    def export():
        path = filedialog.asksaveasfilename(parent=api.root, title="CSV の保存先", defaultextension=".csv",
                                            initialfile=f"workmonitor_{date.today()}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        apps = sorted({k for d in api.data["days"].values() for k in d})
        # Excel で文字化けしないよう BOM 付き UTF-8 にする
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["日付", "合計（分）"] + apps)
            for day in sorted(api.data["days"]):
                rec = api.data["days"][day]
                wr.writerow([day, round(sum(rec.values()) / 60, 1)] + [round(rec.get(a, 0) / 60, 1) for a in apps])
        api.notify(f"📄 {len(api.data['days'])} 日分を書き出しました")
        api.log("保存:", path)

    api.add_action("CSV に書き出す", export)


def teardown(api):
    api.save_data()
