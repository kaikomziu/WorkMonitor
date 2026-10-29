"""休憩の質チェック

長く作業したあとの休憩が短すぎたら（すぐ戻ってきたら）、もう少し休むようにすすめます。
"""

import time

MOD_INFO = {
    "name": "休憩の質チェック",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "45分以上作業したあと、休憩が3分未満ですぐ戻ってきたら「もう少し休もう」と知らせます。",
    "api": 1,
}

LONG_WORK = 45 * 60
MIN_BREAK = 3 * 60


def setup(api):
    s = {"work": 0, "last": None, "break_start": None, "before": 0}

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["work"] += status["today_sec"] - last

    @api.on("state_change")
    def changed(old, new, status):
        if new == "idle":
            s["break_start"] = time.time()
            s["before"] = s["work"]
        elif new == "working" and s["break_start"]:
            took = time.time() - s["break_start"]
            s["break_start"] = None
            if s["before"] >= LONG_WORK and took < MIN_BREAK:
                api.notify(f"☕ {s['before'] // 60}分 働いたのに休憩は {int(took)}秒だけ。"
                           f"あと数分、画面から離れてみませんか？")
            elif took >= MIN_BREAK:
                s["work"] = 0           # ちゃんと休めたので数え直す
