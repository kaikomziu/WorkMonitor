"""天気

Open-Meteo（登録不要の無料 API）から今の天気を取ってきて、メイン画面に表示します。
場所は 設定 → Mods の「場所を設定」で緯度・経度を入れます（初期は東京）。
"""

import json
import threading
import urllib.parse
import urllib.request
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "天気",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今の天気・気温・今日の最高/最低気温をメイン画面に表示します（Open-Meteo を使用、30分ごとに更新）。",
    "api": 1,
}

# WMO の天気コード → (絵文字, 名前)
CODES = {
    0: ("☀", "快晴"), 1: ("🌤", "晴れ"), 2: ("⛅", "くもりがち"), 3: ("☁", "くもり"),
    45: ("🌫", "霧"), 48: ("🌫", "霧"), 51: ("🌦", "霧雨"), 53: ("🌦", "霧雨"), 55: ("🌦", "霧雨"),
    61: ("🌧", "小雨"), 63: ("🌧", "雨"), 65: ("🌧", "大雨"), 71: ("🌨", "小雪"), 73: ("🌨", "雪"),
    75: ("❄", "大雪"), 80: ("🌦", "にわか雨"), 81: ("🌧", "にわか雨"), 82: ("⛈", "激しいにわか雨"),
    95: ("⛈", "雷雨"), 96: ("⛈", "雷雨"), 99: ("⛈", "雷雨"),
}


def fetch(lat, lon):
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "current_weather": "true",
                                "daily": "temperature_2m_max,temperature_2m_min", "timezone": "auto"})
    with urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{q}", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def setup(api):
    api.data.setdefault("lat", 35.68)
    api.data.setdefault("lon", 139.76)
    api.data.setdefault("place", "東京")
    s = {"text": "読み込み中…"}
    w = {}

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 12))
        w["l"].pack(side="left")
        ttk.Button(frame, text="更新", command=update).pack(side="right")
        render()

    def render():
        if w.get("l") and w["l"].winfo_exists():
            w["l"].configure(text=s["text"])

    def done(text):
        s["text"] = text
        render()

    def update():
        lat, lon, place = api.data["lat"], api.data["lon"], api.data["place"]

        def run():
            try:
                d = fetch(lat, lon)
                cur = d["current_weather"]
                emoji, name = CODES.get(int(cur["weathercode"]), ("🌡", ""))
                hi, lo = d["daily"]["temperature_2m_max"][0], d["daily"]["temperature_2m_min"][0]
                text = f"{emoji} {place} {name} {cur['temperature']:.0f}℃（{lo:.0f}〜{hi:.0f}℃）"
            except Exception as e:
                text = f"天気を取得できませんでした（{e.__class__.__name__}）"
            api.call_soon(done, text)
        threading.Thread(target=run, daemon=True).start()

    def loop():
        update()
        api.after(30 * 60 * 1000, loop)

    def set_place():
        place = simpledialog.askstring("天気", "場所の名前（表示用）", parent=api.root, initialvalue=api.data["place"])
        if place is None:
            return
        lat = simpledialog.askfloat("天気", "緯度（例: 東京 35.68 / 大阪 34.69）", parent=api.root,
                                    initialvalue=api.data["lat"])
        lon = simpledialog.askfloat("天気", "経度（例: 東京 139.76 / 大阪 135.50）", parent=api.root,
                                    initialvalue=api.data["lon"])
        if lat is None or lon is None:
            return
        api.data.update({"place": place, "lat": lat, "lon": lon})
        api.save_data()
        update()

    api.add_panel(build, title="天気")
    api.add_action("場所を設定", set_place)
    loop()
