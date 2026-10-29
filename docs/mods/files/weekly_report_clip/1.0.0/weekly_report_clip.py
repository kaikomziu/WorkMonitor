"""週報コピー

直近7日の作業時間とアプリ別トップをまとめた文章を、クリップボードにコピーします。
"""

from datetime import date, timedelta

MOD_INFO = {
    "name": "週報コピー",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "ボタン1つで直近7日の作業まとめをクリップボードにコピーします。チャットや週報に貼り付けて使えます。",
    "api": 1,
}

WEEKDAYS = "月火水木金土日"


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分"


def setup(api):
    api.data.setdefault("days", {})       # 日付 → {"sec": 秒, "apps": {表示名: 秒}}
    s = {"n": 0}

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = {"sec": status["today_sec"],
                                                     "apps": dict(status["today_by_app"])}
        s["n"] += 1
        if s["n"] % 120 == 0:
            old = (date.today() - timedelta(days=30)).isoformat()
            api.data["days"] = {k: v for k, v in api.data["days"].items() if k >= old}
            api.save_data()

    def copy():
        days = [date.today() - timedelta(days=6 - i) for i in range(7)]
        total, apps, lines = 0, {}, []
        for d in days:
            rec = api.data["days"].get(d.isoformat(), {"sec": 0, "apps": {}})
            total += rec["sec"]
            for k, v in rec["apps"].items():
                apps[k] = apps.get(k, 0) + v
            lines.append(f"・{d:%m/%d}（{WEEKDAYS[d.weekday()]}） {fmt(rec['sec'])}")
        top = sorted(apps.items(), key=lambda kv: -kv[1])[:5]
        text = "\n".join(
            [f"【週報】{days[0]:%m/%d}〜{days[-1]:%m/%d}", f"合計 {fmt(total)}（1日平均 {fmt(total / 7)}）", ""]
            + lines + ["", "よく使ったアプリ"] + [f"{i + 1}. {k} {fmt(v)}" for i, (k, v) in enumerate(top)])
        api.root.clipboard_clear()
        api.root.clipboard_append(text)
        api.notify("📋 週報をクリップボードにコピーしました")

    api.add_action("週報をコピー", copy)


def teardown(api):
    api.save_data()
