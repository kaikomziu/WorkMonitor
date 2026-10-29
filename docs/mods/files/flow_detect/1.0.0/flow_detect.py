"""フロー検知

同じアプリで長く作業が続いたら「フロー状態」と判定して、オーバーレイに 🔥 を出します。
"""

MOD_INFO = {
    "name": "フロー検知",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "同じアプリで30分以上作業が続くとフロー状態と判定し、オーバーレイに🔥を表示して通知します。",
    "api": 1,
}

FLOW_SEC = 30 * 60


def setup(api):
    s = {"app": None, "sec": 0, "last": None, "flow": False}

    def stop():
        s.update({"sec": 0, "flow": False})

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if status["app"] != s["app"]:
            s["app"] = status["app"]
            stop()
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= FLOW_SEC and not s["flow"]:
            s["flow"] = True
            api.notify(f"🔥 {status['app_name']} でフロー状態です！ このまま集中しよう。")

    @api.on("state_change")
    def changed(old, new, status):
        if new != "working":
            stop()

    @api.filter("overlay_text")
    def overlay(text):
        return f"🔥フロー {s['sec'] // 60}分 · {text}" if s["flow"] else text
