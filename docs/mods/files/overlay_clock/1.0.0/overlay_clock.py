"""オーバーレイ時計

オーバーレイの文字の後ろに、現在の時刻を付けます。
"""

from datetime import datetime

MOD_INFO = {
    "name": "オーバーレイ時計",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "オーバーレイに現在時刻（例: 🕒 14:05）を足します。",
    "api": 1,
}


def setup(api):
    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · 🕒 {datetime.now():%H:%M}"
