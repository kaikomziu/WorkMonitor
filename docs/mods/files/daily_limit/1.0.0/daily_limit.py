"""1日の上限

作業しすぎを防ぐために、1日の上限（初期は10時間）を超えたら警告します。
"""

from datetime import date
from tkinter import simpledialog

MOD_INFO = {
    "name": "1日の上限",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今日の作業時間が上限（初期10時間）の9割で予告し、超えたら警告します。オーバーレイに⚠も出します。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("limit_h", 10)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "stage": 0})
    s = {"over": False}

    @api.on("tick")
    def tick(status):
        limit = api.data["limit_h"] * 3600
        t = status["today_sec"]
        s["over"] = t >= limit
        if t >= limit * 0.9 and api.data["stage"] < 1:
            api.data["stage"] = 1
            api.save_data()
            api.notify(f"⏳ もうすぐ今日の上限 {api.data['limit_h']} 時間です。そろそろ切り上げる準備を")
        if t >= limit and api.data["stage"] < 2:
            api.data["stage"] = 2
            api.save_data()
            api.notify(f"⚠ 今日の上限 {api.data['limit_h']} 時間を超えました。今日はもう休みましょう！")

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "stage": 0})
        api.save_data()

    @api.filter("overlay_text")
    def overlay(text):
        return f"⚠ {text}" if s["over"] else text

    def set_limit():
        v = simpledialog.askinteger("1日の上限", "1日の上限（時間）", parent=api.root,
                                    initialvalue=api.data["limit_h"], minvalue=1, maxvalue=24)
        if v:
            api.data["limit_h"] = v
            api.save_data()

    api.add_action("上限を変える", set_limit)
