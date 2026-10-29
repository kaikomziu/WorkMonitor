"""ストレッチ指示

作業45分ごとに、その場でできるストレッチをランダムに1つ教えてくれます。

1.1.0: ストレッチを増量・間隔を変更可能に・同じものが続かないように・今日やった回数を記録
"""

import random
from datetime import date
from tkinter import simpledialog

MOD_INFO = {
    "name": "ストレッチ指示",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業45分（変更可）ごとに、座ったままでもできるストレッチのやり方をランダムに通知します。",
    "api": 1,
}

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
    "🙇 首の横伸ばし：右手で頭を右に軽く倒して10秒、反対も",
    "🦒 あご引き：あごを引いて首の後ろを伸ばす 5秒 ×5",
    "🏋 肩回し：両肩を前に10回、後ろに10回",
    "🦶 かかと上げ：立ってかかとの上げ下げ ×15（ふくらはぎのポンプ）",
    "🧘 前屈：座ったまま上半身を前にたおして、背中を丸めて10秒",
    "🤸 わき腹伸ばし：片手を上げて反対側にたおし10秒、反対も",
    "✋ 前腕ストレッチ：腕を前に出し、手のひらを手前に引いて10秒（マウス腕に効く）",
    "🚶 歩こう：水をくみに行くついでに1分歩こう",
]


def setup(api):
    api.data.setdefault("interval_min", 45)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "count": 0})
    s = {"sec": 0, "last": None, "bag": []}

    def show():
        # 全部出しきるまで同じものが出ないように、袋から1つずつ取り出す
        if not s["bag"]:
            s["bag"] = random.sample(STRETCHES, len(STRETCHES))
        api.data["count"] += 1
        api.save_data()
        api.notify(s["bag"].pop(), title=f"🧘 ストレッチタイム（今日 {api.data['count']} 回目）")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= api.data["interval_min"] * 60:
            s["sec"] = 0
            show()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "count": 0})
        api.save_data()
        s["last"] = None

    def set_interval():
        v = simpledialog.askinteger("ストレッチ指示", "何分作業したら知らせる？", parent=api.root,
                                    initialvalue=api.data["interval_min"], minvalue=10, maxvalue=180)
        if v:
            api.data["interval_min"] = v
            api.save_data()

    api.add_action("ストレッチを1つ出す", show)
    api.add_action("間隔を変える", set_interval)
