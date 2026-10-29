"""時報

毎時ちょうどに、時刻の数だけ（12時間制）チャイムを鳴らします。作業中・休憩中だけ鳴ります。

1.1.0: 鳴らし方（チャイム / ひかえめ / 通知だけ）の切り替え・鳴らす時間帯・30分の時報を追加
"""

import threading
import time
import winsound
from datetime import datetime
from tkinter import simpledialog

MOD_INFO = {
    "name": "時報",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "毎時0分にチャイムで知らせます（3時なら3回）。ひかえめ音・通知だけ・30分の時報・鳴らす時間帯を選べます。"
                   "数えないアプリを使っているときは鳴らしません。",
    "api": 1,
}

MODES = {"chime": "チャイム", "soft": "ひかえめ", "notify": "通知だけ"}


def chime(n):
    winsound.Beep(1046, 150)
    winsound.Beep(784, 250)
    time.sleep(0.3)
    for _ in range(n):
        winsound.Beep(988, 120)
        time.sleep(0.25)


def soft():
    winsound.Beep(660, 120)


def setup(api):
    api.data.setdefault("mode", "chime")
    api.data.setdefault("half", False)
    api.data.setdefault("from", 7)
    api.data.setdefault("to", 23)
    s = {"key": datetime.now().strftime("%H:%M")}

    def ring(now):
        if api.data["mode"] == "notify":
            api.notify(f"🕐 {now:%H:%M} です")
        elif api.data["mode"] == "soft" or now.minute == 30:
            threading.Thread(target=soft, daemon=True).start()
        else:
            n = now.hour % 12 or 12
            threading.Thread(target=chime, args=(n,), daemon=True).start()

    @api.on("tick")
    def tick(status):
        now = datetime.now()
        key = now.strftime("%H:%M")
        if key == s["key"]:
            return
        s["key"] = key
        if now.minute == 0 or (now.minute == 30 and api.data["half"]):
            if api.data["from"] <= now.hour <= api.data["to"] and status["state"] != "excluded":
                ring(now)
                api.log(f"{key} の時報")

    def set_mode():
        names = " / ".join(f"{k}={v}" for k, v in MODES.items())
        v = simpledialog.askstring("時報", f"鳴らし方（{names}）", parent=api.root, initialvalue=api.data["mode"])
        if v and v.strip() in MODES:
            api.data["mode"] = v.strip()
            api.save_data()

    def set_hours():
        a = simpledialog.askinteger("時報", "何時から鳴らす？", parent=api.root,
                                    initialvalue=api.data["from"], minvalue=0, maxvalue=23)
        b = simpledialog.askinteger("時報", "何時まで鳴らす？", parent=api.root,
                                    initialvalue=api.data["to"], minvalue=0, maxvalue=23)
        if a is not None and b is not None:
            api.data.update({"from": a, "to": b})
            api.save_data()

    def toggle_half():
        api.data["half"] = not api.data["half"]
        api.save_data()
        api.log("30分の時報:", "オン" if api.data["half"] else "オフ")

    api.add_action("時報を試す", lambda: ring(datetime.now().replace(minute=0)))
    api.add_action("鳴らし方を変える", set_mode)
    api.add_action("鳴らす時間帯を変える", set_hours)
    api.add_action("30分の時報のオン／オフ", toggle_half)
