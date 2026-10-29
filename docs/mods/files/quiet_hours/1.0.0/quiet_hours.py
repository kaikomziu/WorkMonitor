"""おやすみモード

決めた時間帯（初期は 22:00〜7:00）のあいだ、ほかの MOD の通知をすべて止めます。
止めた通知は 設定 → Mods のこの MOD のログ欄に残ります。
WorkMonitor 本体の通知は止めません。
"""

from datetime import datetime
from tkinter import simpledialog

MOD_INFO = {
    "name": "おやすみモード",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "決めた時間帯（初期 22:00〜7:00）は、ほかの MOD の通知を止めます。止めた通知はログに残ります。",
    "api": 2,   # notify フィルターを使う（WorkMonitor 1.7.0 以降）
}


def setup(api):
    api.data.setdefault("start", "22:00")
    api.data.setdefault("end", "07:00")
    api.data.setdefault("on", True)

    def quiet():
        if not api.data["on"]:
            return False
        now = datetime.now().strftime("%H:%M")
        a, b = api.data["start"], api.data["end"]
        return a <= now < b if a <= b else (now >= a or now < b)

    # ほかの MOD が通知を出すときに呼ばれる。False を返すとその通知は出ない
    @api.filter("notify")
    def mute(text, title, mod_id):
        if mod_id != api.id and quiet():
            api.log(f"🔕 止めた通知（{mod_id}）: {text}")
            return False
        return None

    def set_time():
        a = simpledialog.askstring("おやすみモード", "はじまり（HH:MM）", parent=api.root, initialvalue=api.data["start"])
        b = simpledialog.askstring("おやすみモード", "おわり（HH:MM）", parent=api.root, initialvalue=api.data["end"])
        if a and b:
            api.data.update({"start": a.strip().zfill(5), "end": b.strip().zfill(5)})
            api.save_data()

    def toggle():
        api.data["on"] = not api.data["on"]
        api.save_data()
        api.notify("🔕 おやすみモードをオンにしました" if api.data["on"] else "🔔 おやすみモードをオフにしました")

    api.add_action("時間帯を変える", set_time)
    api.add_action("オン／オフを切り替える", toggle)
