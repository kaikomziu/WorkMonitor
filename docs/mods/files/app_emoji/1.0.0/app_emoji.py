"""アプリ別の絵文字

オーバーレイの先頭に、いま使っているアプリに合った絵文字を付けます。
"""

from tkinter import simpledialog

MOD_INFO = {
    "name": "アプリ別の絵文字",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "オーバーレイの先頭に、アプリやカテゴリに合った絵文字（💻🎨🎵 など）を付けます。自分で追加もできます。",
    "api": 1,
}

# exe 名・表示名・カテゴリに含まれる文字（小文字）→ 絵文字。上から順に調べる
DEFAULT = [
    ("code", "💻"), ("pycharm", "💻"), ("idea", "💻"), ("studio", "💻"), ("terminal", "⌨"), ("cmd", "⌨"),
    ("powershell", "⌨"), ("開発", "💻"),
    ("photoshop", "🎨"), ("illustrator", "🎨"), ("figma", "🎨"), ("clip", "🎨"), ("blender", "🧊"),
    ("デザイン", "🎨"),
    ("chrome", "🌐"), ("edge", "🌐"), ("firefox", "🌐"),
    ("word", "📝"), ("notion", "📝"), ("obsidian", "📝"), ("excel", "📊"), ("powerpoint", "📽"),
    ("discord", "💬"), ("slack", "💬"), ("teams", "💬"), ("zoom", "📹"),
    ("spotify", "🎵"), ("music", "🎵"), ("fl64", "🎹"), ("reaper", "🎚"),
    ("premiere", "🎬"), ("davinci", "🎬"), ("obs", "🎥"),
    ("unity", "🎮"), ("unreal", "🎮"), ("roblox", "🎮"), ("steam", "🎮"),
]


def setup(api):
    api.data.setdefault("custom", [])     # [[文字, 絵文字], ...]（DEFAULT より先に調べる）
    s = {"emoji": ""}

    def pick(status):
        hay = f"{status['app']} {status['app_name']} {status['category']}".lower()
        for key, emoji in api.data["custom"] + DEFAULT:
            if key.lower() in hay:
                return emoji
        return ""

    @api.on("app_change")
    def changed(old_app, new_app, status):
        s["emoji"] = pick(status)

    @api.filter("overlay_text")
    def overlay(text):
        return f"{s['emoji']} {text}" if s["emoji"] else text

    def add():
        st = api.status()
        key = simpledialog.askstring("アプリ別の絵文字", f"アプリ名に含まれる文字（いま: {st['app']}）",
                                     parent=api.root, initialvalue=st["app"].replace(".exe", ""))
        if not key:
            return
        emoji = simpledialog.askstring("アプリ別の絵文字", "付ける絵文字", parent=api.root)
        if emoji:
            api.data["custom"].insert(0, [key, emoji])
            api.save_data()
            s["emoji"] = pick(st)

    s["emoji"] = pick(api.status())
    api.add_action("絵文字を追加する", add)
    api.add_action("追加した絵文字をぜんぶ消す", lambda: (api.data.update(custom=[]), api.save_data()))
