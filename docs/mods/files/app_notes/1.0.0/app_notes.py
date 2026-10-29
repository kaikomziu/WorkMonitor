"""アプリ別メモ

アプリごとにメモを登録しておくと、そのアプリに切り替えたときに通知で教えてくれます。
「Photoshop を開いたら素材フォルダを確認」のような使い方ができます。
"""

import time
from tkinter import messagebox, simpledialog

MOD_INFO = {
    "name": "アプリ別メモ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "アプリにメモを登録すると、そのアプリに切り替えたときに通知します（同じアプリは30分に1回まで）。",
    "api": 1,
}

COOLDOWN = 30 * 60


def setup(api):
    api.data.setdefault("notes", {})      # exe 名 → [表示名, メモ]
    shown = {}

    @api.on("app_change")
    def changed(old_app, new_app, status):
        note = api.data["notes"].get(new_app)
        if note and time.time() - shown.get(new_app, 0) > COOLDOWN:
            shown[new_app] = time.time()
            api.notify(f"📌 {note[1]}", title=f"{note[0]} のメモ")

    def add():
        st = api.status()
        # この画面を開いている間は WorkMonitor が前面なので、前に使っていたアプリを選べるよう exe 名を入力にする
        exe = simpledialog.askstring("アプリ別メモ", "アプリの exe 名（例: code.exe, photoshop.exe）",
                                     parent=api.root, initialvalue=st["app"])
        if not exe:
            return
        exe = exe.strip().lower()
        cur = api.data["notes"].get(exe, [exe, ""])
        text = simpledialog.askstring("アプリ別メモ", f"{exe} に切り替えたときに出すメモ（空なら削除）",
                                      parent=api.root, initialvalue=cur[1])
        if text is None:
            return
        if text.strip():
            name = st["app_name"] if st["app"] == exe else exe
            api.data["notes"][exe] = [name, text.strip()]
        else:
            api.data["notes"].pop(exe, None)
        api.save_data()

    def show_all():
        lines = [f"{v[0]}（{k}）: {v[1]}" for k, v in api.data["notes"].items()]
        messagebox.showinfo("アプリ別メモ", "\n".join(lines) or "まだメモがありません", parent=api.root)

    api.add_action("メモを追加・変更", add)
    api.add_action("メモの一覧", show_all)
