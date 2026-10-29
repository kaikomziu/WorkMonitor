"""Discord に作業時間

Discord に出す文に、今日の作業時間と目標の達成率を足します。
"""

MOD_INFO = {
    "name": "Discord に作業時間",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "Discord のステータスを「🔥 作業中 · 今日 2時間15分（75%）」のようにします。",
    "api": 1,
}


def setup(api):
    # discord_text は裏のスレッドから呼ばれるので、tick で作った文字を読むだけにする
    s = {"tail": ""}

    @api.on("tick")
    def tick(status):
        h, m = divmod(status["today_sec"] // 60, 60)
        tail = f"今日 {h}時間{m:02d}分" if h else f"今日 {m}分"
        if status["goal_min"]:
            tail += "（目標達成！）" if status["goal_done"] else f"（{status['today_sec'] * 100 // (status['goal_min'] * 60)}%）"
        s["tail"] = tail

    @api.filter("discord_text")
    def discord(text, info):
        return f"🔥 {text} · {s['tail']}" if s["tail"] else text
