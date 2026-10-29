"""目標達成ファンファーレ

1日の目標を達成したときに、ファンファーレを鳴らします。
"""

import threading
import time
import winsound

MOD_INFO = {
    "name": "目標達成ファンファーレ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "1日の目標を達成した瞬間にファンファーレを鳴らします。",
    "api": 1,
}

# (周波数 Hz, 長さ ms)
FANFARE = [(523, 120), (659, 120), (784, 120), (1047, 300), (0, 80), (784, 120), (1047, 500)]


def play():
    for freq, ms in FANFARE:
        if freq:
            winsound.Beep(freq, ms)
        else:
            time.sleep(ms / 1000)      # 別スレッドの中なので sleep してよい


def setup(api):
    def start():
        # Beep は鳴り終わるまで止まるので、別スレッドで鳴らす
        threading.Thread(target=play, daemon=True).start()

    @api.on("goal_reached")
    def goal(goal_min, streak):
        start()
        api.notify(f"🎺 目標 {goal_min} 分 達成！（{streak} 日連続）")

    api.add_action("試しに鳴らす", start)
