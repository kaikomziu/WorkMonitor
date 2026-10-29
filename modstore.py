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
import tkinter.font as tkfont
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
FONT = "Yu Gothic UI"
# MOD のアイコンの色（名前から決める）
ICON_COLORS = ["#4f6bed", "#22a06b", "#e2a03f", "#d9534f", "#8e6bd8", "#2bb3c0", "#e57fb0", "#5b8def"]
# 状態 → (表示, 色の種類)
STATE_STYLE = {"new": ("未導入", "gray"), "installed": ("✓ 導入済み", "green"), "manual": ("✓ 導入済み（手動）", "green"),
               "update": ("↻ 更新あり", "orange"), "incompatible": ("要アプリの更新", "red")}


def palette(app):
    """テーマに合わせた色（カードは sv_ttk の背景と同じにして、ボタンの角がなじむようにする）"""
    if app.dark:
        return {"page": "#131416", "card": app.bg, "line": "#2c2f36", "text": "#e8eaf0", "sub": "#9aa1ad",
                "accent": "#7b93ff", "soft": "#232838", "sel": "#7b93ff",
                "gray": ("#9aa1ad", "#26282d"), "green": ("#4cc38a", "#16291f"), "orange": ("#e8b25e", "#2e2414"),
                "red": ("#ef7a76", "#2f1918"), "blue": ("#9fb0ff", "#232838")}
    return {"page": "#eef0f4", "card": app.bg, "line": "#e1e4ea", "text": "#1d2330", "sub": "#6b7280",
            "accent": "#4f6bed", "soft": "#eef1fd", "sel": "#4f6bed",
            "gray": ("#6b7280", "#eceef2"), "green": ("#1d8a5b", "#e3f4ec"), "orange": ("#b26d06", "#fcf1dc"),
            "red": ("#c9443f", "#fdeaea"), "blue": ("#4f6bed", "#eef1fd")}


def jp(text):
    """日本語の前後の空白を消す（Tk は空白でしか折り返さず、変な位置で改行されるため。app.jp と同じ）"""
    return re.sub(r"(?<=[^\x00-\x7f]) | (?=[^\x00-\x7f])", "", str(text))


def short(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


class StoreWindow(tk.Toplevel):
    FILTERS = [("all", "🧩", "すべて"), ("new", "＋", "まだ入れていない"), ("installed", "✓", "入れている"),
               ("update", "↻", "更新がある")]
    SORTS = {"new": "新しい順", "name": "名前順"}

    def __init__(self, app, parent, decorate=None):
        super().__init__(parent)
        self.app, self.parent = app, parent
        self.mods, self.by_id, self.cards = [], {}, {}
        self.selected_id = None
        self.filter = "all"
        self.busy = False
        self.updates = 0
        self.s = app.root.winfo_fpixels("1i") / 96   # 画面の拡大率
        self.c = palette(app)
        self.title("MOD ストア - WorkMonitor")
        self.transient(parent)
        self.iconphoto(False, app.icon_photo)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.configure(bg=self.c["page"])
        self.geometry(f"{self.px(1120)}x{self.px(740)}")
        self.minsize(self.px(860), self.px(520))
        # ボタンの文字を読みやすい大きさに（sv_ttk のボタンを引き継いだ自分用のスタイル）
        st = ttk.Style(self)
        st.configure("Store.TButton", font=(FONT, 10))
        st.configure("Store.Accent.TButton", font=(FONT, 10, "bold"))
        st.configure("Store.Switch.TCheckbutton", font=(FONT, 10))
        self.font_pill = tkfont.Font(self, family=FONT, size=9)

        self._build_header()
        self._build_footer()
        body = tk.Frame(self, bg=self.c["page"])
        body.pack(fill="both", expand=True)
        self._build_sidebar(body)
        self._build_detail(body)
        self._build_grid(body)

        self.bind("<Escape>", lambda e: self.close())
        if decorate:
            decorate(self)   # タイトルバーをテーマに合わせる（app.py から渡す）
        self.grab_set()
        self.e_search.focus_set()
        self.show_detail()
        self.load()

    def px(self, n):
        return int(n * self.s)

    # ---- 部品 ----
    def pill(self, parent, text, kind="blue", bg=None):
        fg, pbg = self.c[kind]
        return tk.Label(parent, text=text, fg=fg, bg=pbg, font=self.font_pill, padx=self.px(8), pady=self.px(1))

    def pills(self, parent, items, width, bg):
        """タグを横に並べ、入りきらなければ次の行へ（Tk には折り返して並べる仕組みがないため）"""
        row, used = None, width
        for text, kind in items:
            w = self.font_pill.measure(text) + self.px(16) + self.px(4)
            if row is None or used + w > width:
                row = tk.Frame(parent, bg=bg)
                row.pack(anchor="w", pady=(0, self.px(4)))
                used = 0
            self.pill(row, text, kind).pack(side="left", padx=(0, self.px(4)))
            used += w

    def button(self, parent, text, command, primary=False, **kw):
        return ttk.Button(parent, text=text, command=command,
                          style="Store.Accent.TButton" if primary else "Store.TButton", **kw)

    def icon(self, parent, mod, size, bg):
        """名前の最初の文字を、色つきの角丸の四角に描いたアイコン"""
        size = self.px(size)
        c = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
        color = ICON_COLORS[sum(map(ord, mod["id"])) % len(ICON_COLORS)]
        r, w = size * 0.28, size
        pts = [r, 0, w - r, 0, w, 0, w, r, w, w - r, w, w, w - r, w, r, w, 0, w, 0, w - r, 0, r, 0, 0]
        c.create_polygon(pts, smooth=True, fill=color, outline="")
        c.create_text(w / 2, w / 2, text=(mod["name"] or "?")[0], fill="#ffffff",
                      font=(FONT, max(9, int(size / self.s * 0.36)), "bold"))
        return c

    # ---- 上（タイトル・検索） ----
    def _build_header(self):
        c = self.c
        head = tk.Frame(self, bg=c["card"])
        head.pack(fill="x")
        inner = tk.Frame(head, bg=c["card"])
        inner.pack(fill="x", padx=self.px(22), pady=(self.px(16), self.px(14)))
        t = tk.Frame(inner, bg=c["card"])
        t.pack(fill="x")
        tk.Label(t, text="🧩 MOD ストア", font=(FONT, 17, "bold"), fg=c["text"], bg=c["card"]).pack(side="left")
        tk.Label(t, text="  公式サイトで公開中の MOD を、ボタン1つで入れたり更新したりできます",
                 font=(FONT, 10), fg=c["sub"], bg=c["card"]).pack(side="left", pady=(self.px(6), 0))
        self.button(t, "↻ 読み込み直す", self.load).pack(side="right")

        row = tk.Frame(inner, bg=c["card"])
        row.pack(fill="x", pady=(self.px(12), 0))
        self.v_q = tk.StringVar()
        self.e_search = ttk.Entry(row, textvariable=self.v_q, font=(FONT, 11))
        self.e_search.pack(side="left", fill="x", expand=True, ipady=self.px(2))
        self.v_q.trace_add("write", lambda *a: self._later_render())
        self.v_sort = tk.StringVar(value=self.SORTS["new"])
        cb = ttk.Combobox(row, textvariable=self.v_sort, values=list(self.SORTS.values()), state="readonly", width=10,
                          font=(FONT, 10))
        cb.pack(side="left", padx=(self.px(10), 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self.render())
        self.l_hint = tk.Label(inner, text="🔍 名前・作者・説明で探せます（スペースで区切ると、すべての言葉を含むものだけ）",
                               font=(FONT, 9), fg=c["sub"], bg=c["card"])
        self.l_hint.pack(anchor="w", pady=(self.px(6), 0))
        tk.Frame(self, bg=c["line"], height=1).pack(fill="x")

    # ---- 左（絞り込み） ----
    def _build_sidebar(self, body):
        c = self.c
        side = tk.Frame(body, bg=c["page"], width=self.px(200))
        side.pack(side="left", fill="y", padx=(self.px(14), 0), pady=self.px(14))
        side.pack_propagate(False)
        tk.Label(side, text="表示する MOD", font=(FONT, 9, "bold"), fg=c["sub"], bg=c["page"]).pack(anchor="w", padx=self.px(8),
                                                                                              pady=(0, self.px(6)))
        self.nav = {}
        for key, ico, label in self.FILTERS:
            item = tk.Frame(side, bg=c["page"], cursor="hand2")
            item.pack(fill="x", pady=self.px(1))
            a = tk.Label(item, text=ico, width=2, font=(FONT, 11), bg=c["page"], fg=c["sub"])
            a.pack(side="left", padx=(self.px(8), self.px(4)), pady=self.px(7))
            b = tk.Label(item, text=label, font=(FONT, 10), bg=c["page"], fg=c["text"], anchor="w")
            b.pack(side="left", fill="x", expand=True)
            n = tk.Label(item, text="", font=(FONT, 9), bg=c["page"], fg=c["sub"])
            n.pack(side="right", padx=self.px(10))
            for w in (item, a, b, n):
                w.bind("<Button-1>", lambda e, k=key: self.set_filter(k))
            self.nav[key] = (item, a, b, n)
        tk.Frame(side, bg=c["page"], height=self.px(16)).pack()
        tip = ("⚠ MOD の利用は自己責任です（利用規約 第8条）。自動審査は安全を保証しません。"
               "「中身を見る」で内容を確かめてから入れてください。")
        tk.Label(side, text=jp(tip), font=(FONT, 9), fg=self.c["orange"][0], bg=c["page"], wraplength=self.px(180),
                 justify="left").pack(anchor="w", padx=self.px(8))
        self._paint_nav()

    def _paint_nav(self):
        c = self.c
        for key, (item, a, b, n) in self.nav.items():
            on = key == self.filter
            bg = c["soft"] if on else c["page"]
            for w in (item, a, b, n):
                w.configure(bg=bg)
            a.configure(fg=c["accent"] if on else c["sub"])
            b.configure(fg=c["accent"] if on else c["text"], font=(FONT, 10, "bold" if on else "normal"))

    def set_filter(self, key):
        self.filter = key
        self._paint_nav()
        self.render()
        self.canvas.yview_moveto(0)

    # ---- 右（選んだ MOD の詳しい情報） ----
    def _build_detail(self, body):
        c = self.c
        outer = tk.Frame(body, bg=c["line"], width=self.px(330))
        outer.pack(side="right", fill="y", padx=(0, self.px(14)), pady=self.px(14))
        outer.pack_propagate(False)
        self.detail = tk.Frame(outer, bg=c["card"])
        self.detail.pack(fill="both", expand=True, padx=1, pady=1)

    def show_detail(self):
        c = self.c
        d = self.detail
        for w in d.winfo_children():
            w.destroy()
        m = self.by_id.get(self.selected_id)
        pad = self.px(18)
        if not m:
            tk.Label(d, text="🧩", font=(FONT, 30), bg=c["card"], fg=c["sub"]).pack(pady=(self.px(80), self.px(6)))
            tk.Label(d, text="MOD を選ぶと、ここに\n詳しい情報が出ます", font=(FONT, 10), bg=c["card"], fg=c["sub"],
                     justify="center").pack()
            return
        v = m["versions"][0]
        state, label = state_of(self.app, m)
        top = tk.Frame(d, bg=c["card"])
        top.pack(fill="x", padx=pad, pady=(pad, 0))
        self.icon(top, m, 52, c["card"]).pack(side="left")
        names = tk.Frame(top, bg=c["card"])
        names.pack(side="left", fill="x", expand=True, padx=(self.px(12), 0))
        tk.Label(names, text=m["name"], font=(FONT, 13, "bold"), bg=c["card"], fg=c["text"], anchor="w",
                 wraplength=self.px(220), justify="left").pack(anchor="w")
        tk.Label(names, text=f"v{m['version']} ・ {m['author']}", font=(FONT, 9), bg=c["card"], fg=c["sub"]).pack(anchor="w")
        badge, kind = STATE_STYLE[state]
        if state == "update":
            badge = label.replace("更新あり", "↻ 更新あり")
        self.pill(d, badge if state != "incompatible" else label, kind).pack(anchor="w", padx=pad, pady=(self.px(10), 0))

        btns = tk.Frame(d, bg=c["card"])
        btns.pack(fill="x", padx=pad, pady=(self.px(12), 0))
        text = {"new": "入れる", "update": "更新する", "installed": "入れ直す", "manual": "ストアの版で入れ直す",
                "incompatible": "WorkMonitor の更新が必要"}[state]
        self.b_act = self.button(btns, text, lambda: self.act(m), primary=state in ("new", "update"),
                                 state="disabled" if state == "incompatible" or self.busy else "normal")
        self.b_act.pack(fill="x", ipady=self.px(2))
        links = tk.Frame(d, bg=c["card"])
        links.pack(fill="x", padx=pad, pady=(self.px(6), 0))
        self.button(links, "中身を見る", lambda: webbrowser.open(core.WEBSITE_URL + v["file"])) \
            .pack(side="left", fill="x", expand=True)
        self.button(links, "サイトで見る", lambda: webbrowser.open(core.MODS_URL + f"?q={m['id']}#find")) \
            .pack(side="left", fill="x", expand=True, padx=(self.px(6), 0))

        def section(title):
            tk.Label(d, text=title, font=(FONT, 9, "bold"), bg=c["card"], fg=c["sub"]).pack(anchor="w", padx=pad,
                                                                                         pady=(self.px(14), self.px(4)))
        section("説明")
        tk.Label(d, text=jp(m["description"]), font=(FONT, 10), bg=c["card"], fg=c["text"], wraplength=self.px(290),
                 justify="left").pack(anchor="w", padx=pad)
        if v.get("changes"):
            section(f"v{v['version']} の更新内容")
            tk.Label(d, text=jp(v["changes"]), font=(FONT, 9), bg=c["card"], fg=c["text"], wraplength=self.px(290),
                     justify="left").pack(anchor="w", padx=pad)
        section("この MOD が行うこと")
        perms = v.get("permissions") or []
        if not perms:
            tk.Label(d, text="通信・ファイル操作なし", font=(FONT, 9), bg=c["card"], fg=c["green"][0]).pack(anchor="w", padx=pad)
        box = tk.Frame(d, bg=c["card"])
        box.pack(fill="x", padx=pad)
        self.pills(box, [(PERMISSIONS.get(p, p), "orange" if p in ("network", "file_write", "wm_logs", "notify_filter")
                          else "blue") for p in perms], self.px(290), c["card"])
        section("情報")
        when = str(m.get("updated", ""))[:10]
        tk.Label(d, text=f"ID: {m['id']}\n大きさ: {v['size'] / 1024:.1f}KB ・ 公開: {when}\n"
                         f"必要: WorkMonitor {API_APP.get(v.get('api', 1), '最新版')} 以降",
                 font=(FONT, 9), bg=c["card"], fg=c["sub"], justify="left").pack(anchor="w", padx=pad)

    # ---- 中央（カード） ----
    def _build_grid(self, body):
        c = self.c
        wrap = tk.Frame(body, bg=c["page"])
        wrap.pack(side="left", fill="both", expand=True, padx=self.px(14), pady=(self.px(14), 0))
        self.canvas = tk.Canvas(wrap, bg=c["page"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.grid_frame = tk.Frame(self.canvas, bg=c["page"])
        self.grid_win = self.canvas.create_window(0, 0, window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        self.ncols = 0
        self.empty = tk.Label(self.grid_frame, text="", font=(FONT, 11), bg=c["page"], fg=c["sub"])
        # ホイールでスクロール（このウィンドウの上にいるときだけ）
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, e):
        try:
            if str(e.widget).startswith(str(self)) and self.winfo_exists():
                self.canvas.yview_scroll(int(-e.delta / 120) * 3, "units")
        except tk.TclError:
            pass

    def _on_resize(self, e):
        self.canvas.itemconfigure(self.grid_win, width=e.width)
        n = max(1, min(4, e.width // self.px(250)))
        # 説明文はカードの幅いっぱいで折り返す
        wrap = max(self.px(150), e.width // n - self.px(12) - self.px(30))
        for parts in self.cards.values():
            parts["desc"].configure(wraplength=wrap)
        self.desc_wrap = wrap
        if n != self.ncols:
            self.ncols = n
            self._layout()

    def make_card(self, m):
        c = self.c
        v = m["versions"][0]
        card = tk.Frame(self.grid_frame, bg=c["card"], highlightthickness=1, highlightbackground=c["line"],
                        highlightcolor=c["line"], cursor="hand2")
        inner = tk.Frame(card, bg=c["card"])
        inner.pack(fill="both", expand=True, padx=self.px(14), pady=self.px(12))
        top = tk.Frame(inner, bg=c["card"])
        top.pack(fill="x")
        self.icon(top, m, 40, c["card"]).pack(side="left")
        names = tk.Frame(top, bg=c["card"])
        names.pack(side="left", fill="x", expand=True, padx=(self.px(10), 0))
        tk.Label(names, text=short(m["name"], 22), font=(FONT, 11, "bold"), bg=c["card"], fg=c["text"],
                 anchor="w").pack(anchor="w", fill="x")
        tk.Label(names, text=f"{short(m['author'], 14)} ・ v{m['version']}", font=(FONT, 9), bg=c["card"],
                 fg=c["sub"], anchor="w").pack(anchor="w", fill="x")
        desc = tk.Label(inner, text=jp(short(m["description"], 70)), font=(FONT, 9), bg=c["card"], fg=c["text"],
                        wraplength=getattr(self, "desc_wrap", self.px(220)), justify="left", anchor="nw", height=3)
        desc.pack(anchor="w", fill="x", pady=(self.px(8), 0))
        tags = tk.Frame(inner, bg=c["card"])
        tags.pack(fill="x", pady=(self.px(6), 0))
        perms = v.get("permissions") or []
        if "network" in perms:
            self.pill(tags, "🌐 通信", "orange").pack(side="left", padx=(0, self.px(4)))
        shown = [p for p in perms if p in ("panel", "overlay", "notify", "discord", "sound")][:2]
        for p in shown:
            self.pill(tags, {"panel": "画面", "overlay": "オーバーレイ", "notify": "通知", "discord": "Discord",
                             "sound": "音"}[p]).pack(side="left", padx=(0, self.px(4)))
        if (v.get("api") or 1) > 1:
            self.pill(tags, f"{API_APP.get(v['api'], '新')}〜", "gray").pack(side="left")
        foot = tk.Frame(inner, bg=c["card"])
        foot.pack(fill="x", pady=(self.px(10), 0))
        state_lbl = tk.Label(foot, font=(FONT, 9, "bold"), bg=c["card"])
        state_lbl.pack(side="left")
        btn = self.button(foot, "", lambda: self.act(m), width=8)
        btn.pack(side="right")
        self.cards[m["id"]] = {"frame": card, "state": state_lbl, "btn": btn, "desc": desc}

        def bind_all_children(w):
            if not isinstance(w, ttk.Button):
                w.bind("<Button-1>", lambda e: self.select(m["id"]))
                w.bind("<Enter>", lambda e: self._hover(m["id"], True))
                w.bind("<Leave>", lambda e: self._hover(m["id"], False))
            for ch in w.winfo_children():
                bind_all_children(ch)
        bind_all_children(card)
        self.paint_card(m)
        return card

    def paint_card(self, m):
        c = self.c
        parts = self.cards.get(m["id"])
        if not parts:
            return
        state, label = state_of(self.app, m)
        text, kind = STATE_STYLE[state]
        parts["state"].configure(text=text, fg=c[kind][0])
        btn = {"new": ("入れる", "Store.Accent.TButton"), "update": ("更新", "Store.Accent.TButton"),
               "installed": ("入れ直す", "Store.TButton"), "manual": ("入れ直す", "Store.TButton"),
               "incompatible": ("—", "Store.TButton")}[state]
        parts["btn"].configure(text=btn[0], style=btn[1],
                               state="disabled" if state == "incompatible" or self.busy else "normal")
        sel = m["id"] == self.selected_id
        parts["frame"].configure(highlightthickness=2 if sel else 1,
                                 highlightbackground=c["sel"] if sel else c["line"],
                                 highlightcolor=c["sel"] if sel else c["line"])

    def _hover(self, mod_id, on):
        parts = self.cards.get(mod_id)
        if parts and mod_id != self.selected_id:
            parts["frame"].configure(highlightbackground=self.c["accent"] if on else self.c["line"])

    def select(self, mod_id):
        prev, self.selected_id = self.selected_id, mod_id
        for i in (prev, mod_id):
            if i in self.by_id:
                self.paint_card(self.by_id[i])
        self.show_detail()

    # ---- 一覧 ----
    def close(self):
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
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
        self.mods = mods
        self.by_id = {m["id"]: m for m in mods}
        for parts in self.cards.values():
            parts["frame"].destroy()
        self.cards = {}
        for m in mods:
            self.make_card(m)
        if self.selected_id not in self.by_id:
            self.selected_id = None
        self.render()
        self.show_detail()

    def _later_render(self):
        if getattr(self, "_render_job", None):
            self.after_cancel(self._render_job)
        self._render_job = self.after(150, self.render)

    def visible(self):
        q = [w for w in self.v_q.get().lower().split() if w]
        result, counts = [], {k: 0 for k, _, _ in self.FILTERS}
        for m in self.mods:
            state = state_of(self.app, m)[0]
            text = f"{m['name']} {m['author']} {m['description']} {m['id']}".lower()
            if not all(w in text for w in q):
                continue
            group = {"new": "new", "update": "update", "installed": "installed", "manual": "installed"}.get(state)
            counts["all"] += 1
            if group:
                counts[group] += 1
            if state == "update":
                counts["installed"] += 1   # 更新があるものも「入れている」に数える
            if self.filter == "all" or self.filter == group or (self.filter == "installed" and state == "update"):
                result.append(m)
        if self.v_sort.get() == self.SORTS["name"]:
            result.sort(key=lambda m: m["name"])
        else:
            result.sort(key=lambda m: (str(m.get("updated", "")), m["name"]), reverse=True)
        return result, counts

    def render(self):
        self._render_job = None
        if not self.winfo_exists():
            return
        self.order, counts = self.visible()
        for key, (_, _, _, n) in self.nav.items():
            n.configure(text=str(counts[key]))
        self.updates = sum(1 for m in self.mods if state_of(self.app, m)[0] == "update")
        self.b_all.configure(text=f"↻ すべて更新（{self.updates}）",
                             state="normal" if self.updates and not self.busy else "disabled")
        for m in self.mods:
            self.paint_card(m)
        self._layout()
        if not self.busy:
            self.status(f"{len(self.mods)} 個の MOD があります（表示 {len(self.order)} 個）"
                        + (f"・{self.updates} 個の MOD に更新があります" if self.updates else ""))

    def _layout(self):
        if not self.ncols or not hasattr(self, "order"):
            return
        for parts in self.cards.values():
            parts["frame"].grid_forget()
        self.empty.grid_forget()
        for col in range(6):
            self.grid_frame.columnconfigure(col, weight=1 if col < self.ncols else 0, uniform="card" if col < self.ncols else "")
        gap = self.px(6)
        for i, m in enumerate(self.order):
            self.cards[m["id"]]["frame"].grid(row=i // self.ncols, column=i % self.ncols, sticky="nsew",
                                              padx=gap, pady=gap)
        if not self.order:
            text = "条件に合う MOD がありません" if self.mods else "読み込んでいます…"
            self.empty.configure(text=text)
            self.empty.grid(row=0, column=0, columnspan=self.ncols, pady=self.px(60))

    # ---- 下（まとめて更新・自動更新・状態） ----
    def _build_footer(self):
        c = self.c
        tk.Frame(self, bg=c["line"], height=1).pack(side="bottom", fill="x")
        foot = tk.Frame(self, bg=c["card"])
        foot.pack(side="bottom", fill="x")
        foot.lift()
        inner = tk.Frame(foot, bg=c["card"])
        inner.pack(fill="x", padx=self.px(22), pady=self.px(10))
        self.b_all = self.button(inner, "↻ すべて更新", self.update_all)
        self.b_all.pack(side="left")
        self.v_auto = tk.BooleanVar(value=self.app.earo.settings.get("auto_update", False))
        ttk.Checkbutton(inner, text="ストアから入れた MOD を自動で更新する（1日1回）", variable=self.v_auto,
                        style="Store.Switch.TCheckbutton", command=self._set_auto).pack(side="left", padx=self.px(14))
        self.l_status = tk.Label(inner, text="", font=(FONT, 9), bg=c["card"], fg=c["sub"])
        self.l_status.pack(side="right")

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

    def act(self, m=None):
        m = m or self.by_id.get(self.selected_id)
        if not m or self.busy or state_of(self.app, m)[0] == "incompatible" or not self._agreed():
            return
        self.select(m["id"])
        self._run([m])

    def update_all(self):
        targets = [m for m in self.mods if state_of(self.app, m)[0] == "update"]
        if targets and not self.busy and self._agreed():
            self._run(targets)

    def _run(self, targets):
        self.busy = True
        for m in targets:
            parts = self.cards.get(m["id"])
            if parts:
                parts["btn"].configure(text="…", state="disabled")
        self.b_all.configure(state="disabled")
        if hasattr(self, "b_act") and self.b_act.winfo_exists():
            self.b_act.configure(state="disabled", text="入れています…")
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
        self.show_detail()
        if done:
            self.status(f"✓ {'、'.join(done)} を入れました")
        if failed:
            messagebox.showwarning("MOD ストア", "\n".join(failed), parent=self)
