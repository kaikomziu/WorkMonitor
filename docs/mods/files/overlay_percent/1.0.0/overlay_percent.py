"""オーバーレイに達成率

オーバーレイの文字の先頭に、1日の目標の達成率を付けます。
"""

MOD_INFO = {
    "name": "オーバーレイに達成率",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "オーバーレイの先頭に目標の達成率（例: 63%）を付けます。達成したら ✅ になります。",
    "api": 1,
}


def setup(api):
    s = {"text": ""}

    @api.on("tick")
    def tick(status):
        goal = status["goal_min"] * 60
        if not goal:
            s["text"] = ""
        elif status["today_sec"] >= goal:
            s["text"] = "✅"
        else:
            s["text"] = f"{status['today_sec'] * 100 // goal}%"

    @api.filter("overlay_text")
    def overlay(text):
        return f"{s['text']} {text}" if s["text"] else text
