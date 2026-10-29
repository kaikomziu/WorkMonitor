"""目標達成を Webhook に投稿

1日の目標を達成したら、Discord や Slack の Webhook にメッセージを送ります。
URL は 設定 → Mods の「Webhook の URL を設定」で入れてください。
"""

import json
import threading
import urllib.request
from tkinter import simpledialog

MOD_INFO = {
    "name": "目標達成を Webhook に投稿",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "目標を達成したら Discord / Slack の Webhook に「🎉 目標達成！」を投稿します。URL は自分で設定します。",
    "api": 1,
}


def post(url, text):
    # Discord は content、Slack は text を読むので両方入れる
    body = json.dumps({"content": text, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "WorkMonitor-mod"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def setup(api):
    api.data.setdefault("url", "")
    api.data.setdefault("name", "")

    def send(text):
        url = api.data["url"]
        if not url:
            api.log("Webhook の URL が設定されていません")
            return

        def run():
            try:
                code = post(url, text)
                api.call_soon(api.log, f"送信しました（{code}）")
            except Exception as e:
                api.call_soon(api.log, f"送信に失敗しました: {e}")
        threading.Thread(target=run, daemon=True).start()

    @api.on("goal_reached")
    def goal(goal_min, streak):
        who = api.data["name"] or "わたし"
        h, m = divmod(goal_min, 60)
        send(f"🎉 {who} が今日の目標（{h}時間{m:02d}分）を達成しました！ {streak} 日連続 🔥")

    def set_url():
        v = simpledialog.askstring("Webhook", "Discord / Slack の Webhook の URL", parent=api.root,
                                   initialvalue=api.data["url"])
        if v is None:
            return
        if v and not v.startswith("https://"):
            api.log("https:// で始まる URL を入れてください")
            return
        api.data["url"] = v.strip()
        n = simpledialog.askstring("Webhook", "投稿に出す名前（空なら「わたし」）", parent=api.root,
                                   initialvalue=api.data["name"])
        if n is not None:
            api.data["name"] = n.strip()
        api.save_data()

    api.add_action("Webhook の URL を設定", set_url)
    api.add_action("テスト送信", lambda: send("✅ WorkMonitor からのテスト投稿です"))
