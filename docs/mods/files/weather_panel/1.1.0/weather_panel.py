"""天気

Open-Meteo（登録不要の無料 API）から今の天気を取ってきて、メイン画面に表示します。
場所は 設定 → Mods の「場所を設定」で入れます（初期は東京）。

1.1.0: 都市名で場所を検索・この先6時間の降水確率・雨が近づいたら通知・体感温度を追加
"""

import json
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

MOD_INFO = {
    "name": "天気",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "今の天気・気温・最高/最低気温と、この先6時間の降水確率をメイン画面に表示します。雨が近いと通知。"
                   "場所は都市名で検索できます（Open-Meteo を使用、30分ごとに更新）。",
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
RAIN_WARN = 60      # この降水確率（%）以上が近づいたら通知


def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch(lat, lon):
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 2,
                                "current": "temperature_2m,apparent_temperature,weather_code",
                                "hourly": "precipitation_probability",
                                "daily": "temperature_2m_max,temperature_2m_min"})
    return get_json(f"https://api.open-meteo.com/v1/forecast?{q}")


def geocode(name):
    # 日本語は「大阪」では見つからず「大阪市」なら見つかることがあるので、市を付けてもう一度さがす
    for n in (name, name + "市"):
        q = urllib.parse.urlencode({"name": n, "count": 1, "language": "ja"})
        res = get_json(f"https://geocoding-api.open-meteo.com/v1/search?{q}").get("results") or []
        if res:
            return res[0]
    return None


def setup(api):
    api.data.setdefault("lat", 35.68)
    api.data.setdefault("lon", 139.76)
    api.data.setdefault("place", "東京")
    s = {"text": "読み込み中…", "rain": "", "warned": ""}
    w = {}

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        w["l"] = ttk.Label(top, font=("Segoe UI", 12))
        w["l"].pack(side="left")
        ttk.Button(top, text="更新", command=update).pack(side="right")
        w["rain"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["rain"].pack(anchor="w")
        render()

    def render():
        if w.get("l") and w["l"].winfo_exists():
            w["l"].configure(text=s["text"])
            w["rain"].configure(text=s["rain"])

    def done(text, rain, warn):
        s.update({"text": text, "rain": rain})
        render()
        if warn and warn != s["warned"]:
            s["warned"] = warn
            api.notify(warn)

    def update():
        lat, lon, place = api.data["lat"], api.data["lon"], api.data["place"]

        def run():
            rain, warn = "", ""
            try:
                d = fetch(lat, lon)
                cur = d["current"]
                emoji, name = CODES.get(int(cur["weather_code"]), ("🌡", ""))
                hi, lo = d["daily"]["temperature_2m_max"][0], d["daily"]["temperature_2m_min"][0]
                text = (f"{emoji} {place} {name} {cur['temperature_2m']:.0f}℃"
                        f"（体感 {cur['apparent_temperature']:.0f}℃ · {lo:.0f}〜{hi:.0f}℃）")
                # この先6時間の降水確率
                now = datetime.now().strftime("%Y-%m-%dT%H:00")
                times = d["hourly"]["time"]
                i = times.index(now) if now in times else 0
                probs = d["hourly"]["precipitation_probability"][i:i + 6]
                hours = [t[11:13] for t in times[i:i + 6]]
                rain = "☂ " + "  ".join(f"{h}時 {p}%" for h, p in zip(hours, probs))
                for h, p in zip(hours[1:], probs[1:]):
                    if p is not None and p >= RAIN_WARN:
                        warn = f"☂ {h}時ごろ雨が降りそう（{p}%）。洗濯物や帰り道に注意！"
                        break
            except Exception as e:
                text = f"天気を取得できませんでした（{e.__class__.__name__}）"
            api.call_soon(done, text, rain, warn)
        threading.Thread(target=run, daemon=True).start()

    def loop():
        update()
        api.after(30 * 60 * 1000, loop)

    def set_place():
        name = simpledialog.askstring("天気", "都市名（例: 大阪市、札幌、Osaka、New York）", parent=api.root,
                                      initialvalue=api.data["place"])
        if not name:
            return

        def run():
            try:
                r = geocode(name)
            except Exception as e:
                r = e
            api.call_soon(found, r)

        def found(r):
            if isinstance(r, Exception) or not r:
                messagebox.showerror("天気", f"「{name}」が見つかりませんでした", parent=api.root)
                return
            api.data.update({"place": r.get("name", name), "lat": r["latitude"], "lon": r["longitude"]})
            api.save_data()
            api.log(f"場所: {r.get('name')}（{r.get('country', '')}） {r['latitude']}, {r['longitude']}")
            update()
        threading.Thread(target=run, daemon=True).start()

    api.add_panel(build, title="天気")
    api.add_action("場所を設定", set_place)
    loop()
