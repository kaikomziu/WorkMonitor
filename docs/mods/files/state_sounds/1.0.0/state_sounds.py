"""状態変化の効果音

作業を始めたとき・休憩に入ったとき・数えないアプリに切り替えたときに、ちがう音を鳴らします。
"""

import threading
import winsound

MOD_INFO = {
    "name": "状態変化の効果音",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業開始は「ピロン↑」、休憩は「ポロン↓」、数えないアプリは「ブッ」と、状態が変わるたびに音で知らせます。",
    "api": 1,
}

SOUNDS = {
    "working":  [(660, 80), (880, 120)],
    "idle":     [(880, 80), (660, 120)],
    "excluded": [(220, 150)],
}


def play(notes):
    for freq, ms in notes:
        winsound.Beep(freq, ms)


def setup(api):
    @api.on("state_change")
    def changed(old, new, status):
        if old and new in SOUNDS:
            threading.Thread(target=play, args=(SOUNDS[new],), daemon=True).start()

    for state, name in (("working", "作業開始"), ("idle", "休憩"), ("excluded", "数えないアプリ")):
        api.add_action(f"「{name}」の音を試す",
                       lambda st=state: threading.Thread(target=play, args=(SOUNDS[st],), daemon=True).start())
