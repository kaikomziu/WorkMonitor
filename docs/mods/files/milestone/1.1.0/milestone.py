"""マイルストーン通知

今日の作業時間が区切り（初期は1時間ごと）を超えるたびに褒めてくれます。

1.1.0: 区切りの間隔を変更可能に（15分〜）・ことばを増量・区切りで短い音
"""

import threading
import winsound
from datetime import date
from tkinter import simpledialog

MOD_INFO = {
    "name": "マイルストーン通知",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "今日の作業時間が区切り（初期1時間、変更可）を超えるたびに、ほめる通知と短い音を出します。",
    "api": 1,
}

WORDS = ["いい調子！", "その調子！", "すごい集中力！", "がんばってますね！", "ナイスペース！", "えらい！",
         "積み上がってます！", "今日のあなた、最高です", "このままいこう！", "休憩も忘れずに☕", "天才では？",
         "記録更新も見えてきた！"]


def setup(api):
    api.data.setdefault("step_min", 60)
    api.data.setdefault("sound", True)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "hour": None})

    def step():
        return api.data["step_min"] * 60

    @api.on("tick")
    def tick(status):
        n = status["today_sec"] // step()
        if api.data["hour"] is None:          # 起動直後は今の値から数え始める
            api.data["hour"] = n
        if n > api.data["hour"]:
            api.data["hour"] = n
            api.save_data()
            h, m = divmod(n * api.data["step_min"], 60)
            done = f"{h}時間{m:02d}分" if m else f"{h}時間"
            api.notify(f"⏱ 今日 {done} 作業しました。{WORDS[n % len(WORDS)]}")
            if api.data["sound"]:
                threading.Thread(target=lambda: (winsound.Beep(880, 90), winsound.Beep(1175, 140)),
                                 daemon=True).start()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "hour": 0})
        api.save_data()

    def set_step():
        v = simpledialog.askinteger("マイルストーン通知", "何分ごとに知らせる？", parent=api.root,
                                    initialvalue=api.data["step_min"], minvalue=15, maxvalue=240)
        if v:
            api.data["step_min"] = v
            api.data["hour"] = api.status()["today_sec"] // (v * 60)
            api.save_data()

    def toggle_sound():
        api.data["sound"] = not api.data["sound"]
        api.save_data()

    api.add_action("間隔を変える", set_step)
    api.add_action("音のオン／オフ", toggle_sound)
