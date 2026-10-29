"""姿勢チェック

作業中、ランダムな間隔（20〜40分）で「姿勢はだいじょうぶ？」と声をかけます。
"""

import random

MOD_INFO = {
    "name": "姿勢チェック",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業中に20〜40分のランダムな間隔で、背筋・肩・画面との距離などの姿勢チェックを通知します。",
    "api": 1,
}

CHECKS = [
    "🪑 背筋、伸びてる？ 骨盤を立てて座り直そう",
    "😬 肩に力が入ってない？ ストンと落としてみて",
    "🖥 画面に顔が近づいてない？ 腕の長さくらい離そう",
    "🦶 足の裏、床についてる？",
    "🐢 首が前に出てない？ あごを軽く引こう",
    "😮‍💨 呼吸、浅くなってない？ ゆっくり深呼吸",
    "🦷 歯をくいしばってない？ あごの力を抜こう",
]


def setup(api):
    s = {"sec": 0, "next": random.randint(20, 40) * 60, "last": None}

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= s["next"]:
            s["sec"] = 0
            s["next"] = random.randint(20, 40) * 60
            api.notify(random.choice(CHECKS), title="姿勢チェック")

    @api.on("day_change")
    def new_day(day):
        s["last"] = None
