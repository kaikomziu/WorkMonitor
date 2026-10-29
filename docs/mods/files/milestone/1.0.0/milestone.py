"""マイルストーン通知

今日の作業時間が1時間・2時間・3時間…と区切りを超えるたびに褒めてくれます。
"""

from datetime import date

MOD_INFO = {
    "name": "マイルストーン通知",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今日の作業時間が1時間を超えるごとに、ほめる通知を出します。",
    "api": 1,
}

WORDS = ["いい調子！", "その調子！", "すごい集中力！", "がんばってますね！", "ナイスペース！", "えらい！"]


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "hour": None})

    @api.on("tick")
    def tick(status):
        hour = status["today_sec"] // 3600
        if api.data["hour"] is None:          # 起動直後は今の値から数え始める
            api.data["hour"] = hour
        if hour > api.data["hour"]:
            api.data["hour"] = hour
            api.save_data()
            api.notify(f"⏱ 今日 {hour} 時間 作業しました。{WORDS[hour % len(WORDS)]}")

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "hour": 0})
        api.save_data()
