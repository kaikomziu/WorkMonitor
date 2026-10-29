"""MOD ストア（公式サイトで公開中の MOD を、アプリの中からボタン1つで入れる・更新する）

一覧は公式サイトの mods/index.json を読む。ダウンロードしたファイルは一覧の SHA-256 と照らし合わせ、
違えば入れない。入れるのは Earo のいつもの追加の仕組み（mods フォルダへのコピー）を使う。
ストアから入れた MOD は config["mods"]["store"] に覚えておき、自動更新（初期はオフ）の対象にする。
"""

import hashlib
import json
import os
import re
import ssl
import tempfile
import threading
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import messagebox, ttk

import core
import earo

INDEX_URL = core.WEBSITE_URL + "mods/index.json"
FILE_PATH = re.compile(r"^mods/files/[a-z0-9][a-z0-9_-]{1,39}/\d{1,4}(\.\d{1,4}){0,3}/[a-z0-9][a-z0-9_-]{1,39}\.(py|zip)$")
MAX_DOWNLOAD = 1024 * 1024
AUTO_UPDATE_INTERVAL_MS = 24 * 60 * 60 * 1000   # 自動更新を確かめる間隔（1日）
TLS = ssl.create_default_context()
TLS.minimum_version = ssl.TLSVersion.TLSv1_2
# tools/mod_review.py の PERMISSIONS と同じ
PERMISSIONS = {
    "network": "インターネットに接続", "browser": "ブラウザでページを開く", "file_write": "ファイルを書き込む",
    "file_read": "ファイルを読み込む", "wm_logs": "作業記録を読む", "thread": "裏で処理を動かす",
    "panel": "メイン画面に表示を追加", "overlay": "オーバーレイの表示を変える", "discord": "Discord の表示を変える",
    "notify": "通知を出す", "sound": "音を鳴らす", "dialog": "ウィンドウを開く",
    "open": "フォルダやファイルを開く", "notify_filter": "ほかの MOD の通知を止める・変える",
}
API_APP = {1: "1.6.0", 2: "1.7.0"}   # MOD_INFO の api → 必要な WorkMonitor のバージョン
AGREE_TEXT = ("MOD は利用者が作って投稿したプログラムで、このアプリと同じ権限で動きます。"
              "公開前に自動審査をしていますが、安全や動作は保証されません。\n\n"
              "MOD の利用は自己責任です。MOD の利用で生じた損害について、運営者は責任を負いません（利用規約 第8条）。\n\n"
              "同意して MOD ストアを使いますか？")


class StoreError(Exception):
    pass


# ===== 通信 =====
def _get(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": f"{core.APP_NAME}/{core.APP_VERSION}", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, context=TLS, timeout=20) as res:
            data = res.read(limit + 1)
    except OSError as e:
        raise StoreError(f"公式サイトにつながりませんでした（{e}）")
    if len(data) > limit:
        raise StoreError("ファイルが大きすぎます")
    return data


def fetch_index():
    try:
        mods = json.loads(_get(INDEX_URL, 4 * 1024 * 1024)).get("mods", [])
    except ValueError:
        raise StoreError("MOD の一覧を読めませんでした")
    return [m for m in mods if m.get("versions") and FILE_PATH.match(m["versions"][0].get("file", ""))]


def download(version):
    """公開中の版のファイルを取ってきて、一覧の SHA-256 と同じか確かめる → 中身"""
    path = version.get("file", "")
    if not FILE_PATH.match(path):
        raise StoreError("ダウンロード先がおかしいため、入れませんでした")
    data = _get(core.WEBSITE_URL + path, MAX_DOWNLOAD)
    if hashlib.sha256(data).hexdigest() != version.get("sha256"):
        raise StoreError("ダウンロードしたファイルが一覧と違う（改ざんや通信の問題の可能性）ため、入れませんでした")
    return data


def version_key(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return ()


def usable(version):
    """この WorkMonitor（の Earo）で使える版か"""
    return int(version.get("api", 1) or 1) <= earo.API_VERSION


# ===== 入れる・更新する =====
def install(app, mod, data):
    """ダウンロードした MOD を入れる（画面のスレッドで呼ぶ）→ 入った Earo の Mod"""
    loader = app.earo
    v = mod["versions"][0]
    name = v["file"].rsplit("/", 1)[1]
    existing = loader.mods.get(mod["id"])
    updating = existing is not None
    active = loader.is_active(mod["id"]) if updating else True   # 更新ではオン・オフをそのまま
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, name)
        with open(path, "wb") as f:
            f.write(data)
        plan = loader.inspect(path)
        if plan.mod_id != mod["id"]:
            raise StoreError("MOD の名前が一覧と違うため、入れませんでした")
        installed = loader.install(plan, active=active,
                                   note=f"MOD ストアから{'更新' if updating else '追加'}しました（v{v['version']}）")
    loader.settings.setdefault("store", {})[mod["id"]] = {"version": v["version"], "sha256": v["sha256"]}
    core.save_config(app.config)
    return installed


def state_of(app, mod):
    """一覧の MOD の状態 → (状態の名前, 表示)。名前: new / installed / manual / update / incompatible"""
    loader = app.earo
    v = mod["versions"][0]
    local = loader.mods.get(mod["id"])
    rec = loader.settings.get("store", {}).get(mod["id"])
    if not usable(v):
        return "incompatible", f"要 WorkMonitor {API_APP.get(v.get('api'), '最新版')} 以降"
    if local is None:
        return "new", "未導入"
    current = local.info.get("version") or (rec or {}).get("version", "")
    if version_key(v["version"]) > version_key(current):
        return "update", f"更新あり（v{current} → v{v['version']}）"
    return ("installed", "✓ 導入済み") if rec else ("manual", "✓ 導入済み（手動）")


# ===== 自動更新 =====
def auto_update(app, done=None):
    """ストアから入れた MOD に新しい版があれば入れる（自動更新がオンのとき・1日1回）"""
    def worker():
        try:
            mods = fetch_index()
        except StoreError:
            return
        # 何を更新するかは画面のスレッドで決める（Earo の状態を読むため）
        app.events.put(lambda: _apply_updates(app, mods, done))
    threading.Thread(target=worker, daemon=True).start()


def _apply_updates(app, mods, done):
    store = app.earo.settings.get("store", {})
    targets = [m for m in mods if m["id"] in store and m["id"] in app.earo.mods and state_of(app, m)[0] == "update"]
    if not targets:
        return

    def worker():
        results = []
        for m in targets:
            try:
                results.append((m, download(m["versions"][0]), None))
            except StoreError as e:
                results.append((m, None, str(e)))
        app.events.put(lambda: _install_updates(app, results, done))
    threading.Thread(target=worker, daemon=True).start()


def _install_updates(app, results, done):
    updated, failed = [], []
    for m, data, err in results:
        if data is not None:
            try:
                install(app, m, data)
                updated.append(f"{m['name']} v{m['version']}")
                continue
            except (StoreError, earo.InstallError, OSError) as e:
                err = str(e)
        failed.append(f"{m['name']}: {err}")
    if updated:
        app._notify("、".join(updated[:3]) + (f" ほか {len(updated) - 3} 個" if len(updated) > 3 else ""),
                    "MOD を自動で更新しました")
    if done:
        done(updated, failed)


# ===== 画面 =====
class StoreWindow(tk.Toplevel):
    FILTERS = {"all": "すべて", "new": "まだ入れていない", "installed": "入れている", "update": "更新がある"}

    def __init__(self, app, parent, decorate=None):
        super().__init__(parent)
        self.app, self.parent = app, parent
        self.mods, self.by_id = [], {}
        self.title("MOD ストア - WorkMonitor")
        self.transient(parent)
        self.iconphoto(False, app.icon_photo)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.minsize(int(app.wrap * 1.25), 0)

        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="公式サイトで公開中の MOD を、ボタン1つで入れたり更新したりできます。",
                  foreground=app.sub_color).pack(anchor="w")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(10, 6))
        self.v_q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.v_q, font="SunValleyBodyFont")
        e.pack(side="left", fill="x", expand=True)
        self.v_q.trace_add("write", lambda *a: self.render())
        self.v_filter = tk.StringVar(value=self.FILTERS["all"])
        c = ttk.Combobox(top, textvariable=self.v_filter, values=list(self.FILTERS.values()), state="readonly", width=14,
                         font="SunValleyBodyFont")
        c.pack(side="left", padx=8)
        c.bind("<<ComboboxSelected>>", lambda ev: self.render())
        ttk.Button(top, text="↻ 読み込み直す", command=self.load).pack(side="left")

        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        cols = ("name", "author", "version", "state")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=11, selectmode="browse")
        for col, text, w in zip(cols, ("MOD", "作者", "バージョン", "状態"), (230, 100, 80, 190)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="w")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda ev: self.show())
        self.tree.bind("<Double-1>", lambda ev: self.act())

        d = ttk.LabelFrame(f, text="選んだ MOD", padding=12)
        d.pack(fill="x", pady=(10, 0))
        self.l_title = ttk.Label(d, text="（一覧から選んでください）", font=("Yu Gothic UI", 12, "bold"))
        self.l_title.pack(anchor="w")
        self.l_desc = ttk.Label(d, text="", wraplength=int(app.wrap * 1.15), justify="left")
        self.l_desc.pack(anchor="w", pady=(4, 0))
        self.l_meta = ttk.Label(d, text="", foreground=app.sub_color, wraplength=int(app.wrap * 1.15), justify="left")
        self.l_meta.pack(anchor="w", pady=(4, 0))
        b = ttk.Frame(d)
        b.pack(fill="x", pady=(10, 0))
        self.b_act = ttk.Button(b, text="入れる", style="Accent.TButton", command=self.act)
        self.b_act.pack(side="left")
        self.b_code = ttk.Button(b, text="中身を見る", command=self.view_code)
        self.b_code.pack(side="left", padx=8)
        ttk.Button(b, text="サイトで見る", command=lambda: webbrowser.open(core.MODS_URL)).pack(side="left")

        bottom = ttk.Frame(f)
        bottom.pack(fill="x", pady=(10, 0))
        self.b_all = ttk.Button(bottom, text="すべて更新", command=self.update_all)
        self.b_all.pack(side="left")
        self.v_auto = tk.BooleanVar(value=app.earo.settings.get("auto_update", False))
        ttk.Checkbutton(bottom, text="ストアから入れた MOD を自動で更新する（1日1回）", variable=self.v_auto,
                        style="Switch.TCheckbutton", command=self._set_auto).pack(side="left", padx=12)
        self.l_status = ttk.Label(f, text="", foreground=app.sub_color, wraplength=int(app.wrap * 1.15), justify="left")
        self.l_status.pack(anchor="w", pady=(8, 0))
        ttk.Label(f, text="⚠ MOD の利用は自己責任です（利用規約 第8条）。自動審査は安全を保証しません。",
                  foreground="#e2a03f").pack(anchor="w", pady=(4, 0))

        self.busy = False
        self.show()
        self.bind("<Escape>", lambda ev: self.close())
        if decorate:
            decorate(self)   # タイトルバーをテーマに合わせる（app.py から渡す）
        self.grab_set()
        e.focus_set()
        self.load()

    def close(self):
        self.grab_release()
        self.destroy()
        if self.parent.winfo_exists():
            try:
                self.parent.grab_set()   # 設定画面に操作を戻す
            except tk.TclError:
                pass

    def status(self, text):
        if self.winfo_exists():
            self.l_status.configure(text=text)

    # ---- 一覧 ----
    def load(self):
        self.status("公式サイトから一覧を読み込んでいます…")

        def worker():
            try:
                mods, err = fetch_index(), None
            except StoreError as e:
                mods, err = None, str(e)
            self.app.events.put(lambda: self._loaded(mods, err))
        threading.Thread(target=worker, daemon=True).start()

    def _loaded(self, mods, err):
        if not self.winfo_exists():
            return
        if err:
            self.status(err)
            return
        self.app.earo.scan()   # 手で入れたり消したりしたものも反映
        self.mods = sorted(mods, key=lambda m: m["name"])
        self.by_id = {m["id"]: m for m in self.mods}
        self.render()

    def render(self):
        q = [w for w in self.v_q.get().lower().split() if w]
        want = next(k for k, v in self.FILTERS.items() if v == self.v_filter.get())
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        counts = {"update": 0}
        for m in self.mods:
            state, label = state_of(self.app, m)
            counts["update"] += state == "update"
            text = f"{m['name']} {m['author']} {m['description']} {m['id']}".lower()
            if not all(w in text for w in q):
                continue
            if want == "new" and state not in ("new",):
                continue
            if want == "installed" and state not in ("installed", "manual", "update"):
                continue
            if want == "update" and state != "update":
                continue
            self.tree.insert("", "end", iid=m["id"], values=(m["name"], m["author"], f"v{m['version']}", label))
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        shown = len(self.tree.get_children())
        self.updates = counts["update"]
        self.b_all.configure(text=f"すべて更新（{self.updates}）", state="normal" if self.updates and not self.busy else "disabled")
        if not self.busy:
            self.status(f"{len(self.mods)} 個の MOD があります（表示 {shown} 個）"
                        + (f"・更新できる MOD が {self.updates} 個あります" if self.updates else ""))
        self.show()

    def selected(self):
        sel = self.tree.selection()
        return self.by_id.get(sel[0]) if sel else None

    def show(self):
        m = self.selected()
        if not m:
            self.l_title.configure(text="（一覧から選んでください）")
            self.l_desc.configure(text="")
            self.l_meta.configure(text="")
            self.b_act.configure(state="disabled", text="入れる")
            self.b_code.configure(state="disabled")
            return
        v = m["versions"][0]
        state, label = state_of(self.app, m)
        perms = "・".join(PERMISSIONS.get(p, p) for p in v.get("permissions", [])) or "通信・ファイル操作なし"
        self.l_title.configure(text=f"{m['name']}  v{m['version']}")
        desc = m["description"] + (f"\n更新内容: {v['changes']}" if v.get("changes") else "")
        self.l_desc.configure(text=desc)
        self.l_meta.configure(text=f"作者: {m['author']} ・ {m['id']} ・ {v['size'] / 1024:.1f}KB ・ 状態: {label}\n"
                                   f"この MOD が行うこと: {perms}")
        text = {"new": "入れる", "update": "更新する", "installed": "入れ直す", "manual": "ストアの版で入れ直す",
                "incompatible": "WorkMonitor の更新が必要"}[state]
        self.b_act.configure(text=text, state="disabled" if state == "incompatible" or self.busy else "normal")
        self.b_code.configure(state="normal")

    def view_code(self):
        m = self.selected()
        if m:
            webbrowser.open(core.WEBSITE_URL + m["versions"][0]["file"])

    def _set_auto(self):
        self.app.earo.settings["auto_update"] = self.v_auto.get()
        core.save_config(self.app.config)

    # ---- 入れる ----
    def _agreed(self):
        settings = self.app.earo.settings
        if settings.get("store_agreed"):
            return True
        if not messagebox.askyesno("MOD ストア", AGREE_TEXT, icon="warning", parent=self):
            return False
        settings["store_agreed"] = True
        core.save_config(self.app.config)
        return True

    def act(self):
        m = self.selected()
        if not m or self.busy or state_of(self.app, m)[0] == "incompatible" or not self._agreed():
            return
        self._run([m])

    def update_all(self):
        targets = [m for m in self.mods if state_of(self.app, m)[0] == "update"]
        if targets and not self.busy and self._agreed():
            self._run(targets)

    def _run(self, targets):
        self.busy = True
        self.b_act.configure(state="disabled")
        self.b_all.configure(state="disabled")
        self.status(f"ダウンロードしています…（{len(targets)} 個）")

        def worker():
            results = []
            for m in targets:
                try:
                    results.append((m, download(m["versions"][0]), None))
                except StoreError as e:
                    results.append((m, None, str(e)))
            self.app.events.put(lambda: self._downloaded(results))
        threading.Thread(target=worker, daemon=True).start()

    def _downloaded(self, results):
        done, failed = [], []
        for m, data, err in results:
            if data is not None:
                try:
                    mod = install(self.app, m, data)
                    if mod.status == "error":
                        failed.append(f"{m['name']}: 入れましたが、読み込めませんでした（{mod.error}）")
                    else:
                        done.append(m["name"])
                    continue
                except (StoreError, earo.InstallError, OSError) as e:
                    err = str(e)
            failed.append(f"{m['name']}: {err}")
        self.busy = False
        if not self.winfo_exists():
            return
        self.render()
        msg = (f"{'、'.join(done)} を入れました。" if done else "") + ("\n" + "\n".join(failed) if failed else "")
        self.status(msg.strip())
        if failed:
            messagebox.showwarning("MOD ストア", "\n".join(failed), parent=self)
