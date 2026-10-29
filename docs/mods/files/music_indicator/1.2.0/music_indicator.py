"""音楽モード

Spotify などの音楽アプリを前面で使うと「音楽モード」になり、オーバーレイに 🎵 を出します。
音楽を聴きながらの作業時間と、聴かずにした作業時間を分けて記録します。

1.2.0: 曲名を読むのをやめて（ctypes を使わない）、音楽アプリを開いたことで判定する形に作り直し。
       音楽あり／なしの作業時間の比較・手動の切り替えボタンを追加
"""

import time
from datetime import date, timedelta
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "音楽モード",
    "version": "1.2.0",
    "author": "かるわか",
    "description": "Spotify・iTunes・YouTube Music などの音楽アプリを開くと音楽モードになり、オーバーレイに🎵を出します。"
                   "音楽あり／なしの作業時間を比べられます。",
    "api": 1,
}

# 音楽アプリとみなす exe 名・表示名に含まれる文字（小文字）
DEFAULT_APPS = ["spotify", "itunes", "applemusic", "aimp", "foobar2000", "musicbee", "winamp",
                "youtube music", "amazon music", "line music", "groove", "mediaplayer"]
KEEP_HOURS = 2      # 最後に音楽アプリを見てから、この時間たったら音楽モードを自動で終わる


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    api.data.setdefault("apps", [])        # 自分で足した音楽アプリ
    api.data.setdefault("history", {})     # 日付 → [音楽ありの作業秒, なしの作業秒]
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "with": 0, "without": 0})
    s = {"on": False, "app": "", "seen": 0, "last": None, "n": 0}
    w = {}

    def is_music(status):
        hay = f"{status['app']} {status['app_name']}".lower()
        return any(k in hay for k in DEFAULT_APPS + api.data["apps"])

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        w["l"] = ttk.Label(top, font=("Segoe UI", 12))
        w["l"].pack(side="left")
        w["btn"] = ttk.Button(top, command=toggle)
        w["btn"].pack(side="right")
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"], justify="left")
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        w["l"].configure(text=f"🎵 音楽モード（{s['app']}）" if s["on"] else "🔇 音楽なし")
        w["btn"].configure(text="音楽をやめた" if s["on"] else "音楽を聴いている")
        a, b = api.data["with"], api.data["without"]
        total = a + b
        ratio = f"（音楽あり {a * 100 // total}%）" if total else ""
        # 直近7日で、音楽あり／なしのどちらの日によく作業できたか
        days = [(date.today() - timedelta(days=i)).isoformat() for i in range(1, 8)]
        wa = sum(api.data["history"].get(d, [0, 0])[0] for d in days)
        wb = sum(api.data["history"].get(d, [0, 0])[1] for d in days)
        week = f"\n直近7日: 音楽あり {fmt(wa)} · なし {fmt(wb)}" if wa or wb else ""
        w["sub"].configure(text=f"今日 音楽あり {fmt(a)} · なし {fmt(b)}{ratio}{week}")

    def turn_on(name):
        s.update({"on": True, "app": name, "seen": time.time()})
        render()

    def turn_off():
        s.update({"on": False, "app": ""})
        render()

    def toggle():
        if s["on"]:
            turn_off()
        else:
            turn_on("手動")

    @api.on("app_change")
    def changed(old_app, new_app, status):
        if is_music(status):
            if not s["on"]:
                api.log(f"音楽モード開始: {status['app_name']}")
            turn_on(status["app_name"])

    @api.on("tick")
    def tick(status):
        if s["on"] and is_music(status):
            s["seen"] = time.time()
        if s["on"] and s["app"] != "手動" and time.time() - s["seen"] > KEEP_HOURS * 3600:
            turn_off()
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            api.data["with" if s["on"] else "without"] += status["today_sec"] - last
        s["n"] += 1
        if s["n"] % 60 == 0:
            api.save_data()
        if s["n"] % 10 == 0:
            render()

    @api.on("day_change")
    def new_day(day):
        api.data["history"][api.data["day"]] = [api.data["with"], api.data["without"]]
        keep = sorted(api.data["history"])[-30:]
        api.data["history"] = {k: api.data["history"][k] for k in keep}
        api.data.update({"day": day, "with": 0, "without": 0})
        s["last"] = None
        api.save_data()
        render()

    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · 🎵" if s["on"] else text

    def add_app():
        st = api.status()
        v = simpledialog.askstring("音楽モード", "音楽アプリの exe 名や名前に含まれる文字（例: vlc）",
                                   parent=api.root, initialvalue=st["app"].replace(".exe", ""))
        if v and v.strip():
            api.data["apps"].append(v.strip().lower())
            api.save_data()

    api.add_panel(build, title="音楽モード")
    api.add_action("音楽アプリを追加", add_app)
    api.add_action("音楽モードの切り替え", toggle)


def teardown(api):
    api.save_data()
