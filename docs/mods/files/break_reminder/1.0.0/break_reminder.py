"""休憩リマインダー

休まずに作業が続いたら、休憩をすすめる通知を出します。
"""

from tkinter import simpledialog

MOD_INFO = {
    "name": "休憩リマインダー",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "連続で作業した時間が一定（初期は60分）を超えると休憩をすすめます。休憩中が3分続くとリセット。",
    "api": 1,
}

RESET_IDLE_SEC = 180   # この秒数だけ休憩が続いたら「休んだ」とみなす
REPEAT_MIN = 15        # 休まなかったときに、もう一度知らせるまでの分


def setup(api):
    api.data.setdefault("limit_min", 60)
    s = {"work": 0, "idle": 0, "next": 0, "last": None}

    def reset():
        s["work"] = 0
        s["next"] = api.data["limit_min"] * 60

    reset()

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if status["state"] == "working":
            s["idle"] = 0
            if last is not None and status["today_sec"] > last:
                s["work"] += status["today_sec"] - last
        else:
            s["idle"] += 1
            if s["idle"] >= RESET_IDLE_SEC:
                reset()
        if s["work"] >= s["next"]:
            api.notify(f"⏸ {s['work'] // 60}分 休まず作業しています。少し休憩しませんか？")
            s["next"] += REPEAT_MIN * 60

    def set_limit():
        v = simpledialog.askinteger("休憩リマインダー", "何分続けて作業したら知らせる？", parent=api.root,
                                    initialvalue=api.data["limit_min"], minvalue=5, maxvalue=600)
        if v:
            api.data["limit_min"] = v
            api.save_data()
            reset()

    api.add_action("知らせる時間を変える", set_limit)
    api.add_action("いま休んだことにする", reset)
