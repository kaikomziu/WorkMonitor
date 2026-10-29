"""時報

毎時ちょうどに、時刻の数だけ（12時間制）チャイムを鳴らします。作業中・休憩中だけ鳴ります。
"""

import threading
import time
import winsound
from datetime import datetime

MOD_INFO = {
    "name": "時報",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "毎時0分にチャイムで知らせます（3時なら3回）。数えないアプリを使っているときは鳴らしません。",
    "api": 1,
}


def chime(n):
    winsound.Beep(1046, 150)
    winsound.Beep(784, 250)
    time.sleep(0.3)
    for _ in range(n):
        winsound.Beep(988, 120)
        time.sleep(0.25)


def setup(api):
    s = {"hour": datetime.now().hour}

    @api.on("tick")
    def tick(status):
        now = datetime.now()
        if now.hour != s["hour"] and now.minute == 0:
            s["hour"] = now.hour
            if status["state"] != "excluded":
                n = now.hour % 12 or 12
                threading.Thread(target=chime, args=(n,), daemon=True).start()
                api.log(f"{now.hour}時の時報")

    api.add_action("時報を試す", lambda: threading.Thread(target=chime, args=(3,), daemon=True).start())
