"""20-20-20 ルール

20分作業するたびに「20フィート（約6m）先を20秒見よう」と知らせる、目のための MOD です。
"""

MOD_INFO = {
    "name": "20-20-20 ルール",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業20分ごとに、20秒間 遠く（6m先）を見るように知らせて目の疲れを防ぎます。",
    "api": 1,
}

INTERVAL = 20 * 60


def setup(api):
    s = {"sec": 0, "last": None}

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= INTERVAL:
            s["sec"] = 0
            api.notify("👀 20秒だけ、6m くらい先の遠くを見て目を休めましょう。")
            api.after(20_000, lambda: api.notify("✅ OK！ 作業に戻りましょう。"))

    @api.on("state_change")
    def changed(old, new, status):
        if new == "idle":      # 休憩したら数え直す
            s["sec"] = 0
