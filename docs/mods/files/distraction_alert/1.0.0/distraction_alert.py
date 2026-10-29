"""脱線警告

数えないアプリ（動画・SNS など）を使い続けていたら「作業に戻ろう」と知らせます。
"""

from tkinter import simpledialog

MOD_INFO = {
    "name": "脱線警告",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "数えないアプリを続けて5分（変更可）使うと、作業に戻るよう通知します。そのあとも5分ごとに知らせます。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("limit_min", 5)
    s = {"sec": 0}

    @api.on("tick")
    def tick(status):
        if status["state"] != "excluded":
            s["sec"] = 0
            return
        s["sec"] += 1
        if s["sec"] % (api.data["limit_min"] * 60) == 0:
            api.notify(f"👀 {status['app_name']} を {s['sec'] // 60}分 使っています。そろそろ作業に戻りませんか？")

    def set_limit():
        v = simpledialog.askinteger("脱線警告", "何分たったら知らせる？", parent=api.root,
                                    initialvalue=api.data["limit_min"], minvalue=1, maxvalue=120)
        if v:
            api.data["limit_min"] = v
            api.save_data()

    api.add_action("知らせる時間を変える", set_limit)
