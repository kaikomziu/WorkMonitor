"""ストレッチ指示

作業45分ごとに、その場でできるストレッチをランダムに1つ教えてくれます。
"""

import random

MOD_INFO = {
    "name": "ストレッチ指示",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業45分ごとに、座ったままでもできるストレッチのやり方をランダムに通知します。",
    "api": 1,
}

INTERVAL = 45 * 60

STRETCHES = [
    "🙆 首回し：ゆっくり右に5回、左に5回まわそう",
    "💪 肩すくめ：肩を耳に近づけて5秒キープ → ストンと落とす ×5",
    "🤲 手首ほぐし：手を組んで手首をくるくる10回",
    "🙌 背伸び：両手を組んで頭の上へ。10秒ぐーっと伸びよう",
    "🔄 体ひねり：座ったまま上半身を右へ10秒、左へ10秒",
    "🦵 足首回し：片足ずつ足首を10回まわそう",
    "🧍 立ち上がって：その場で軽く足踏み30秒",
    "👐 胸ひらき：背中で手を組んで胸を開き、10秒キープ",
    "🖐 指ストレッチ：指を1本ずつ反らして伸ばそう",
    "😌 深呼吸：4秒吸って、7秒止めて、8秒で吐く ×3",
    "🐱 猫背リセット：肩甲骨をぎゅっと寄せて5秒 ×5",
    "👀 目のストレッチ：上下左右を見て、ぎゅっと閉じてパッと開く",
]


def setup(api):
    s = {"sec": 0, "last": None}

    def show():
        api.notify(random.choice(STRETCHES), title="🧘 ストレッチタイム")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= INTERVAL:
            s["sec"] = 0
            show()

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    api.add_action("ストレッチを1つ出す", show)
