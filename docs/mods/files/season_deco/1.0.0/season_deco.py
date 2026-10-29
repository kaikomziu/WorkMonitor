"""季節のかざり

日付に合わせて、オーバーレイに季節の絵文字を付けます。
"""

from datetime import date

MOD_INFO = {
    "name": "季節のかざり",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "お正月🎍・バレンタイン🍫・桜🌸・ハロウィン🎃・クリスマス🎄など、日付に合った絵文字をオーバーレイに付けます。",
    "api": 1,
}

# (開始 月日, 終了 月日, 絵文字) … 上にあるものほど優先
EVENTS = [
    ((1, 1), (1, 7), "🎍"),
    ((2, 3), (2, 3), "👹"),
    ((2, 10), (2, 14), "🍫"),
    ((3, 1), (3, 3), "🎎"),
    ((3, 14), (3, 14), "🍬"),
    ((4, 29), (5, 5), "🎏"),
    ((7, 7), (7, 7), "🎋"),
    ((8, 10), (8, 16), "🎆"),
    ((10, 25), (10, 31), "🎃"),
    ((12, 20), (12, 25), "🎄"),
    ((12, 26), (12, 31), "🎍"),
    # 季節
    ((3, 20), (4, 15), "🌸"),
    ((6, 1), (6, 30), "☔"),
    ((7, 1), (8, 31), "🌻"),
    ((9, 1), (9, 30), "🎑"),
    ((10, 1), (11, 30), "🍁"),
    ((12, 1), (2, 28), "⛄"),
]


def deco(today):
    md = (today.month, today.day)
    for start, end, emoji in EVENTS:
        if start <= end and start <= md <= end:
            return emoji
        if start > end and (md >= start or md <= end):     # 年をまたぐ期間
            return emoji
    return ""


def setup(api):
    @api.filter("overlay_text")
    def overlay(text):
        e = deco(date.today())
        return f"{e} {text}" if e else text
