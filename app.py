"""作業監視ツール（GUI 版）

ウィンドウを閉じてもタスクトレイに常駐して記録を続ける。
設定（放置判定・アプリ別ルール・オーバーレイ・Discord）はアプリ内の設定画面から変更できる。
"""

import copy
import ctypes
import os
import queue
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
import winreg
from tkinter import messagebox, ttk

import sv_ttk
from PIL import ImageTk

import app_icon
import core
from dashboard import build_dashboard
from overlay import Overlay

try:
    import pystray
except ImportError:
    pystray = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DISCORD_PORTAL_URL = "https://discord.com/developers/applications"
FONT = "Yu Gothic UI"
EXCLUDED_COLOR = "#e2a03f"
BODY_FONT = "SunValleyBodyFont"  # sv_ttk の本文フォント（入力欄もこれに揃える）


# ===== Windows 連携 =====
def launch_command():
    """自動起動に登録するコマンド（exe 版 / Python 版の両対応）"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pythonw}" "{os.path.abspath(__file__)}" --minimized'


def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, core.APP_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, core.APP_NAME)
            except FileNotFoundError:
                pass


def acquire_single_instance():
    """二重起動を防ぐ。すでに起動していれば None を返す"""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = k32.CreateMutexW(None, False, f"{core.APP_NAME}_SingleInstance")
    ERROR_ALREADY_EXISTS = 183
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def windows_uses_dark_mode():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def dark_title_bar(window, dark):
    """タイトルバーもテーマに合わせる（Windows 11）"""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass


def jp(text):
    """日本語の前後の空白を消す（Tk は空白でしか折り返さず、変な位置で改行されるため）"""
    return re.sub(r"(?<=[^\x00-\x7f]) | (?=[^\x00-\x7f])", "", text)


def fmt_hms(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def fmt_hm(sec):
    sec = int(sec)
    return f"{sec // 3600}時間{sec % 3600 // 60:02d}分"


# ===== 設定画面 =====
class SettingsDialog(tk.Toplevel):
    def __init__(self, app, tab=0):
        super().__init__(app.root)
        self.app = app
        self.cfg = copy.deepcopy(app.config)   # 保存するまでは本体の設定を変えない
        self.title("設定 - WorkMonitor")
        self.resizable(False, False)
        self.transient(app.root)
        self.iconphoto(False, app.icon_photo)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(outer)
        self.nb.pack(fill="both", expand=True)
        self._tab_general()
        self._tab_apps()
        self._tab_overlay()
        self._tab_discord()
        self.nb.select(tab)

        b = ttk.Frame(outer)
        b.pack(fill="x", pady=(14, 0))
        ttk.Button(b, text="キャンセル", command=self.cancel).pack(side="right")
        ttk.Button(b, text="保存", style="Accent.TButton", command=self.save).pack(side="right", padx=8)

        dark_title_bar(self, app.dark)
        self.bind("<Escape>", lambda e: self.cancel())
        self.grab_set()
        self.focus_set()

    def _page(self, title, desc):
        f = ttk.Frame(self.nb, padding=18)
        self.nb.add(f, text=title)
        ttk.Label(f, text=jp(desc), foreground=self.app.sub_color, wraplength=self.app.wrap, justify="left") \
            .pack(anchor="w", pady=(0, 12))
        return f

    def _row(self, parent, label, widget_factory, note=None):
        r = ttk.Frame(parent)
        r.pack(fill="x", pady=5)
        ttk.Label(r, text=label).pack(side="left")
        w = widget_factory(r)
        w.pack(side="right")
        if note:
            ttk.Label(parent, text=jp(note), foreground=self.app.sub_color, wraplength=self.app.wrap, justify="left") \
                .pack(anchor="w", pady=(0, 4))
        return w

    def _switch(self, parent, text, var, command=None, note=None):
        ttk.Checkbutton(parent, text=text, variable=var, style="Switch.TCheckbutton", command=command) \
            .pack(anchor="w", pady=5)
        if note:
            ttk.Label(parent, text=jp(note), foreground=self.app.sub_color, wraplength=self.app.wrap, justify="left") \
                .pack(anchor="w", padx=(48, 0), pady=(0, 4))

    # ---- 一般 ----
    def _tab_general(self):
        f = self._page("一般", "記録のしかたと起動の設定です。")
        self.v_idle = tk.StringVar(value=str(self.cfg["idle_threshold_sec"]))
        self._row(f, "無操作で「休憩中」にするまでの秒数",
                  lambda p: ttk.Spinbox(p, font=BODY_FONT, from_=10, to=3600, increment=10, width=8, textvariable=self.v_idle),
                  note="キーボードやマウスをこの秒数さわらないと、作業時間を止めます。読み物が多いなら長めに。")
        ttk.Separator(f).pack(fill="x", pady=10)
        self.v_autostart = tk.BooleanVar(value=self.cfg["autostart"])
        self._switch(f, "Windows の起動時に自動で起動する", self.v_autostart)
        self.v_top = tk.BooleanVar(value=self.cfg["always_on_top"])
        self._switch(f, "メイン画面を常に一番上に表示する", self.v_top)
        ttk.Separator(f).pack(fill="x", pady=10)
        ttk.Button(f, text="記録フォルダを開く", command=self.open_data_dir).pack(anchor="w")

    def open_data_dir(self):
        os.makedirs(core.DATA_DIR, exist_ok=True)
        os.startfile(core.DATA_DIR)

    # ---- アプリ別 ----
    def _tab_apps(self):
        f = self._page("アプリ別", "アプリごとに、作業に数えるか・カテゴリ・Discord に出す文言を決められます。"
                                  "一覧から選んで、下で変更してください（ゲームや動画サイトは「作業に数える」をオフに）。")
        cols = ("name", "category", "count", "discord")
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=7, selectmode="browse")
        for c, text, w in zip(cols, ("アプリ", "カテゴリ", "作業に数える", "Discord の表示"), (170, 120, 90, 160)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=w, anchor="center" if c == "count" else "w")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._load_selected())

        # 編集欄
        ed = ttk.LabelFrame(f, text="選んだアプリの設定", padding=12)
        ed.pack(fill="x", pady=(12, 0))
        self.v_name = tk.StringVar()
        self.v_cat = tk.StringVar()
        self.v_count = tk.BooleanVar()
        self.v_dtext = tk.StringVar()
        self.l_exe = ttk.Label(ed, text="（一覧から選んでください）", foreground=self.app.sub_color)
        self.l_exe.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        ttk.Label(ed, text="表示名").grid(row=1, column=0, sticky="w")
        self.e_name = ttk.Entry(ed, font=BODY_FONT, textvariable=self.v_name, width=20)
        self.e_name.grid(row=1, column=1, sticky="w", padx=(8, 16), pady=3)
        ttk.Label(ed, text="カテゴリ").grid(row=1, column=2, sticky="w")
        self.c_cat = ttk.Combobox(ed, font=BODY_FONT, textvariable=self.v_cat, width=16, values=core.all_categories(self.cfg))
        self.c_cat.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=3)
        ttk.Label(ed, text="Discord の表示").grid(row=2, column=0, sticky="w")
        self.e_dtext = ttk.Entry(ed, font=BODY_FONT, textvariable=self.v_dtext, width=20)
        self.e_dtext.grid(row=2, column=1, sticky="w", padx=(8, 16), pady=3)
        self.sw_count = ttk.Checkbutton(ed, text="作業に数える", variable=self.v_count, style="Switch.TCheckbutton")
        self.sw_count.grid(row=2, column=2, columnspan=2, sticky="w")
        ttk.Label(ed, text="Discord の表示が空欄なら「作業中」と出ます（例: プログラミング中、お絵かき中）",
                  foreground=self.app.sub_color).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.b_reset = ttk.Button(ed, text="初期値に戻す", command=self._reset_selected)
        self.b_reset.grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))

        add = ttk.Frame(f)
        add.pack(fill="x", pady=(10, 0))
        ttk.Label(add, text="一覧にないアプリを追加（exe 名）").pack(side="left")
        self.v_add = tk.StringVar()
        ttk.Button(add, text="追加", command=self._add_app).pack(side="right")
        ttk.Entry(add, font=BODY_FONT, textvariable=self.v_add, width=20).pack(side="right", padx=8)

        self._loading = False
        self._selected = None
        for v in (self.v_name, self.v_cat, self.v_count, self.v_dtext):
            v.trace_add("write", lambda *a: self._store_selected())
        self._set_editor_state(False)
        self._fill_tree()

    def _fill_tree(self, select=None):
        self.tree.delete(*self.tree.get_children())
        apps = core.recent_apps() | {k for k in self.cfg["app_rules"]}
        # 大文字小文字違いの重複をまとめる
        uniq = {}
        for a in apps:
            uniq.setdefault(a.lower(), a)
        rows = sorted(uniq.values(), key=lambda a: (not core.app_info(self.cfg, a)["count"],
                                                   core.app_info(self.cfg, a)["name"].lower()))
        for a in rows:
            self.tree.insert("", "end", iid=a.lower(), values=self._row_values(a))
        if select and self.tree.exists(select.lower()):
            self.tree.selection_set(select.lower())
            self.tree.see(select.lower())

    def _row_values(self, app):
        i = core.app_info(self.cfg, app)
        return (i["name"], i["category"], "✓ 数える" if i["count"] else "✗ 数えない", i["discord"] or "（作業中）")

    def _set_editor_state(self, enabled):
        state = "normal" if enabled else "disabled"
        for w in (self.e_name, self.e_dtext, self.sw_count, self.b_reset):
            w.configure(state=state)
        self.c_cat.configure(state=state)

    def _load_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        info = core.app_info(self.cfg, key)
        self._loading = True
        self._selected = key
        self.v_name.set(info["name"])
        self.v_cat.set(info["category"])
        self.v_count.set(info["count"])
        self.v_dtext.set(info["discord"])
        self._loading = False
        self.l_exe.configure(text=f"対象: {key}")
        self._set_editor_state(True)

    def _store_selected(self):
        if self._loading or not self._selected:
            return
        key = self._selected
        self.cfg["app_rules"][key] = {
            "name": self.v_name.get().strip() or core.app_info({}, key)["name"],
            "category": self.v_cat.get().strip() or core.UNCATEGORIZED,
            "count": bool(self.v_count.get()),
            "discord": self.v_dtext.get().strip(),
        }
        self.tree.item(key, values=self._row_values(key))
        self.c_cat.configure(values=core.all_categories(self.cfg))

    def _reset_selected(self):
        if self._selected:
            self.cfg["app_rules"].pop(self._selected, None)
            self.tree.item(self._selected, values=self._row_values(self._selected))
            self._load_selected()
            self.cfg["app_rules"].pop(self._selected, None)  # 読み込みで書き戻された分も消す

    def _add_app(self):
        name = self.v_add.get().strip()
        if not name:
            return
        if not name.lower().endswith(".exe"):
            name += ".exe"
        key = name.lower()
        self.cfg["app_rules"].setdefault(key, {k: v for k, v in core.app_info(self.cfg, key).items()})
        self.v_add.set("")
        self._fill_tree(select=key)

    # ---- オーバーレイ ----
    def _tab_overlay(self):
        f = self._page("オーバーレイ", "画面の端に小さなタイマーを常に表示します。ゲームや全画面の作業中でも時間が見えます。"
                                     "ドラッグで移動、右クリックでメニュー、ダブルクリックでメイン画面を開きます。")
        o = self.cfg["overlay"]
        self.v_ov_on = tk.BooleanVar(value=o["enabled"])
        self.v_ov_alpha = tk.DoubleVar(value=round(o["opacity"] * 100))
        self.v_ov_size = tk.StringVar(value=o["size"])
        self.v_ov_app = tk.BooleanVar(value=o["show_app"])
        self.v_ov_through = tk.BooleanVar(value=o["click_through"])

        self._switch(f, "オーバーレイを表示する", self.v_ov_on, self._preview_overlay)
        r = ttk.Frame(f)
        r.pack(fill="x", pady=8)
        ttk.Label(r, text="透明度").pack(side="left")
        self.l_alpha = ttk.Label(r, width=5)
        self.l_alpha.pack(side="right")
        ttk.Scale(r, from_=30, to=100, variable=self.v_ov_alpha, length=260,
                  command=lambda v: self._preview_overlay()).pack(side="right", padx=8)
        self._row(f, "大きさ", lambda p: self._size_box(p))
        self._switch(f, "アプリ名とカテゴリも表示する", self.v_ov_app, self._preview_overlay)
        self._switch(f, "クリックを透過する（後ろのウィンドウを操作できる）", self.v_ov_through, self._preview_overlay,
                     note="オンの間はオーバーレイをドラッグできません。動かすときは一度オフにしてください。")
        ttk.Button(f, text="位置を初期化（右上へ）", command=self._reset_overlay_pos).pack(anchor="w", pady=(8, 0))
        self._preview_overlay()

    def _size_box(self, parent):
        c = ttk.Combobox(parent, font=BODY_FONT, textvariable=self.v_ov_size, values=list(("小", "中", "大")), width=6, state="readonly")
        c.bind("<<ComboboxSelected>>", lambda e: self._preview_overlay())
        return c

    def _overlay_cfg(self):
        o = dict(self.cfg["overlay"])
        o.update({
            "enabled": self.v_ov_on.get(),
            "opacity": round(self.v_ov_alpha.get()) / 100,
            "size": self.v_ov_size.get(),
            "show_app": self.v_ov_app.get(),
            "click_through": self.v_ov_through.get(),
        })
        return o

    def _preview_overlay(self):
        """変更をその場でオーバーレイに反映（キャンセルで元に戻す）"""
        self.l_alpha.configure(text=f"{round(self.v_ov_alpha.get())}%")
        o = self._overlay_cfg()
        # 位置は本体側（ドラッグで動いた最新値）を使う
        o["x"], o["y"] = self.app.config["overlay"]["x"], self.app.config["overlay"]["y"]
        self.app.overlay.apply(o)

    def _reset_overlay_pos(self):
        self.app.config["overlay"]["x"] = self.app.config["overlay"]["y"] = None
        self._preview_overlay()

    # ---- Discord ----
    def _tab_discord(self):
        f = self._page("Discord", "Discord のプロフィールに「作業中 1:23:45 経過」のように表示します。"
                                 "PC 版の Discord アプリを起動しておく必要があります。")
        self.v_discord = tk.BooleanVar(value=self.cfg["discord_enabled"])
        self.v_client = tk.StringVar(value=self.cfg["discord_client_id"])
        self.v_show_app = tk.BooleanVar(value=self.cfg["discord_show_app"])
        self._switch(f, "Discord に作業時間を表示する", self.v_discord)
        self._row(f, "Application ID", lambda p: ttk.Entry(p, font=BODY_FONT, width=26, textvariable=self.v_client))
        steps = ("空欄なら組み込みの ID を使います。" if core.DEFAULT_DISCORD_CLIENT_ID else
                 "取得方法: ポータルで「New Application」を作成 → 表示される Application ID をコピーして貼り付け。"
                 "アプリに付けた名前が「〇〇をプレイ中」として表示されます。")
        ttk.Label(f, text=jp(steps), foreground=self.app.sub_color, wraplength=self.app.wrap, justify="left").pack(anchor="w")
        ttk.Button(f, text="Discord Developer Portal を開く",
                   command=lambda: webbrowser.open(DISCORD_PORTAL_URL)).pack(anchor="w", pady=(6, 10))
        self._switch(f, "Discord の表示にアプリ名を入れる（例:「作業中: VS Code」）", self.v_show_app,
                     note="アプリ別設定で Discord の表示を決めたアプリは、そちらが優先されます。フレンドに見える点に注意。")
        ttk.Separator(f).pack(fill="x", pady=10)
        self.l_dstatus = ttk.Label(f, text="")
        self.l_dstatus.pack(anchor="w")
        self._refresh_discord_status()

    def _refresh_discord_status(self):
        if self.winfo_exists():
            self.l_dstatus.configure(text=f"いまの状態: {self.app.monitor.discord_status}")
            self.after(1000, self._refresh_discord_status)

    # ---- 保存 / キャンセル ----
    def save(self):
        try:
            idle = int(self.v_idle.get())
            if not 10 <= idle <= 3600:
                raise ValueError
        except ValueError:
            self.nb.select(0)
            messagebox.showerror("設定", "休憩中にするまでの秒数は 10〜3600 の数字で入力してください。", parent=self)
            return
        client = self.v_client.get().strip()
        if client and not client.isdigit():
            self.nb.select(3)
            messagebox.showerror("設定", "Application ID は数字だけで入力してください。", parent=self)
            return

        cfg = self.cfg
        cfg.update({
            "idle_threshold_sec": idle,
            "autostart": self.v_autostart.get(),
            "always_on_top": self.v_top.get(),
            "discord_enabled": self.v_discord.get(),
            "discord_client_id": client,
            "discord_show_app": self.v_show_app.get(),
        })
        overlay = self._overlay_cfg()
        overlay["x"], overlay["y"] = self.app.config["overlay"]["x"], self.app.config["overlay"]["y"]
        cfg["overlay"] = overlay
        try:
            set_autostart(cfg["autostart"])
        except OSError as e:
            messagebox.showerror("設定", f"自動起動の設定に失敗しました。\n{e}", parent=self)
            return
        self.app.apply_config(cfg)
        self.destroy()

    def cancel(self):
        self.app.overlay.apply(self.app.config["overlay"])  # プレビューを元に戻す
        self.destroy()


# ===== メイン画面 =====
class App:
    def __init__(self, start_minimized=False):
        self.config = core.load_config()
        self.monitor = core.Monitor(self.config)
        self.events = queue.Queue()  # タスクトレイ（別スレッド）からの操作
        self.settings = None
        self.tray = None
        self.tray_state = None
        self.tray_notified = False

        self.root = tk.Tk()
        self.root.title("WorkMonitor")
        self.root.resizable(False, False)
        self.dark = windows_uses_dark_mode()
        sv_ttk.set_theme("dark" if self.dark else "light")
        self._setup_fonts()
        self.sub_color = "#9aa1ad" if self.dark else "#6b7280"
        self.wrap = int(560 * self.root.winfo_fpixels("1i") / 96)  # 説明文の折り返し幅
        self.bg = ttk.Style().lookup("TFrame", "background") or ("#1c1c1c" if self.dark else "#fafafa")

        self.icon_photo = ImageTk.PhotoImage(app_icon.make_image(64))
        self.root.iconphoto(True, self.icon_photo)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        dark_title_bar(self.root, self.dark)

        self.overlay = Overlay(self.root, self._overlay_moved, self.show,
                               lambda: self.open_settings(tab=2), lambda: self.set_overlay(False))
        self._apply_window_options()

        # exe を移動しても自動起動が切れないよう、起動のたびに登録し直す
        if self.config["autostart"]:
            try:
                set_autostart(True)
            except OSError:
                pass

        self.monitor.start()
        self._start_tray()
        if start_minimized and self.tray:
            self.root.withdraw()
        self.tick()

    def _setup_fonts(self):
        # sv_ttk のフォントを日本語が読みやすいものに
        for name in tkfont.names(self.root):
            if name.startswith("SunValley") or name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
                tkfont.nametofont(name, self.root).configure(family=FONT)

    def _build(self):
        f = ttk.Frame(self.root, padding=(22, 16, 22, 18))
        f.pack(fill="both", expand=True)

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="今日の作業時間", foreground=self.sub_color).pack(side="left")
        self.v_top = tk.BooleanVar(value=self.config["always_on_top"])
        ttk.Checkbutton(top, text="最前面", variable=self.v_top, style="Switch.TCheckbutton",
                        command=self._toggle_top).pack(side="right")

        self.l_time = ttk.Label(f, text="0:00:00", font=("Segoe UI", 38, "bold"))
        self.l_time.pack(anchor="w", pady=(2, 0))

        # 状態表示（色つきの丸 + 文字）
        st = ttk.Frame(f)
        st.pack(fill="x")
        self.c_dot = tk.Canvas(st, width=14, height=14, highlightthickness=0, bg=self.bg)
        self.c_dot.pack(side="left", padx=(2, 8))
        self.l_state = ttk.Label(st, text="", font=(FONT, 11, "bold"))
        self.l_state.pack(side="left")
        self.l_state_sub = ttk.Label(f, text="", foreground=self.sub_color)
        self.l_state_sub.pack(anchor="w", pady=(2, 0))

        # 今日のカテゴリ別
        ttk.Separator(f).pack(fill="x", pady=12)
        ttk.Label(f, text="今日のカテゴリ別", foreground=self.sub_color).pack(anchor="w")
        self.c_cats = tk.Canvas(f, width=340, height=10, highlightthickness=0, bg=self.bg)
        self.c_cats.pack(fill="x", pady=(6, 0))
        self._cats_key = None
        # 幅が決まったら描き直す
        self.c_cats.bind("<Configure>", lambda e: setattr(self, "_cats_key", None))

        ttk.Separator(f).pack(fill="x", pady=12)
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="📊 ダッシュボード", style="Accent.TButton", command=self.open_dashboard) \
            .pack(side="left", fill="x", expand=True)
        self.v_overlay = tk.BooleanVar(value=self.config["overlay"]["enabled"])
        ttk.Checkbutton(b, text="🪟 オーバーレイ", variable=self.v_overlay, style="Toggle.TButton",
                        command=lambda: self.set_overlay(self.v_overlay.get())) \
            .pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(b, text="⚙ 設定", command=self.open_settings).pack(side="left", fill="x", expand=True)

        self.l_discord = ttk.Label(f, text="", foreground=self.sub_color, font=BODY_FONT)
        self.l_discord.pack(anchor="w", pady=(12, 0))

    # ---- 状態の描画 ----
    def _state_view(self):
        """(色, 見出し, 補足, オーバーレイの2行目)"""
        m = self.monitor
        info = core.app_info(self.config, m.app) if m.app else None
        if m.state == "working":
            return (app_icon.GREEN, "作業中", f"{info['name']}（{info['category']}）", f"{info['name']} · {info['category']}")
        if m.state == "excluded":
            return (EXCLUDED_COLOR, "数えないアプリを使用中", f"{info['name']} は作業時間に入りません", f"{info['name']}（対象外）")
        return (app_icon.GRAY, "休憩中", "キーボードやマウスを操作すると再開します", "休憩中")

    def _draw_categories(self):
        cats = sorted(self.monitor.today_by_category().items(), key=lambda x: -x[1])
        key = tuple((c, int(s // 60)) for c, s in cats)
        if key == self._cats_key:
            return
        self._cats_key = key
        c = self.c_cats
        c.delete("all")
        dpi = self.root.winfo_fpixels("1i") / 96
        row = int(22 * dpi)
        if not cats:
            c.configure(height=row)
            c.create_text(0, row // 2, text="まだ記録がありません", anchor="w", fill=self.sub_color, font=BODY_FONT)
            return
        cats = cats[:5]
        colors = core.category_colors(self.config)
        width = int(c.winfo_width()) if c.winfo_width() > 10 else int(340 * dpi)
        # 列の幅は実際の文字幅から決める
        body = tkfont.nametofont(BODY_FONT, self.root)
        label_w = int(14 * dpi) + max(body.measure(cat) for cat, _ in cats) + int(12 * dpi)
        time_w = body.measure("00時間00分") + int(12 * dpi)
        bar_w = max(int(40 * dpi), width - label_w - time_w)
        top = cats[0][1] or 1
        fg = "#e8eaf0" if self.dark else "#1d2330"
        track = "#2c3039" if self.dark else "#e9ebef"
        c.configure(height=row * len(cats))
        for i, (cat, sec) in enumerate(cats):
            y = i * row + row // 2
            color = colors.get(cat, core.UNCATEGORIZED_COLOR)
            c.create_oval(0, y - 4 * dpi, 8 * dpi, y + 4 * dpi, fill=color, outline="")
            c.create_text(14 * dpi, y, text=cat, anchor="w", fill=fg, font=BODY_FONT)
            x0 = label_w
            c.create_rectangle(x0, y - 3 * dpi, x0 + bar_w, y + 3 * dpi, fill=track, outline="")
            c.create_rectangle(x0, y - 3 * dpi, x0 + max(2, bar_w * sec / top), y + 3 * dpi, fill=color, outline="")
            c.create_text(width, y, text=fmt_hm(sec), anchor="e", fill=fg, font=BODY_FONT)

    # ---- タスクトレイ ----
    def _start_tray(self):
        if pystray is None:
            return
        put = self.events.put
        menu = pystray.Menu(
            pystray.MenuItem("開く", lambda: put("show"), default=True),
            pystray.MenuItem("ダッシュボード", lambda: put("dashboard")),
            pystray.MenuItem("オーバーレイ", lambda: put("overlay"),
                             checked=lambda item: self.config["overlay"]["enabled"]),
            pystray.MenuItem("設定", lambda: put("settings")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("終了", lambda: put("quit")),
        )
        self.tray = pystray.Icon(core.APP_NAME, app_icon.make_image(64, app_icon.GRAY), "WorkMonitor", menu)
        self.tray.run_detached()

    def _update_tray(self, color, text):
        if not self.tray:
            return
        if color != self.tray_state:
            self.tray.icon = app_icon.make_image(64, color)
            self.tray_state = color
        if self.tray.title != text:
            self.tray.title = text

    # ---- 定期更新 ----
    def tick(self):
        while not self.events.empty():
            ev = self.events.get()
            if ev == "show":
                self.show()
            elif ev == "dashboard":
                self.open_dashboard()
            elif ev == "overlay":
                self.set_overlay(not self.config["overlay"]["enabled"])
            elif ev == "settings":
                self.open_settings()
            elif ev == "quit":
                self.quit()
                return

        m = self.monitor
        color, head, sub, line2 = self._state_view()
        self.l_time.configure(text=fmt_hms(m.today_sec))
        self.l_state.configure(text=head, foreground=color)
        self.l_state_sub.configure(text=sub)
        self.c_dot.delete("all")
        self.c_dot.create_oval(1, 1, 13, 13, fill=color, outline="")
        self.l_discord.configure(text=f"Discord: {m.discord_status}")
        self._draw_categories()
        self.overlay.update(fmt_hms(m.today_sec), color, line2)
        self._update_tray(color, f"今日の作業 {fmt_hm(m.today_sec)}（{head}）")
        self.root.after(500, self.tick)

    # ---- 操作 ----
    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self):
        if not self.tray:
            self.quit()
            return
        self.root.withdraw()
        if not self.tray_notified:
            try:
                self.tray.notify("タスクトレイで記録を続けています。終了はアイコンの右クリックから。", "WorkMonitor")
            except Exception:
                pass
            self.tray_notified = True

    def _apply_window_options(self):
        self.root.attributes("-topmost", self.config["always_on_top"])
        self.v_top.set(self.config["always_on_top"])
        self.v_overlay.set(self.config["overlay"]["enabled"])
        self.overlay.apply(self.config["overlay"])

    def _toggle_top(self):
        self.config["always_on_top"] = self.v_top.get()
        self.apply_config(self.config)

    def set_overlay(self, enabled):
        self.config["overlay"]["enabled"] = enabled
        self.apply_config(self.config)

    def _overlay_moved(self, x, y):
        self.config["overlay"]["x"], self.config["overlay"]["y"] = x, y
        core.save_config(self.config)

    def open_dashboard(self):
        try:
            build_dashboard(self.config)
        except OSError as e:
            messagebox.showerror("ダッシュボード", f"開けませんでした。\n{e}")

    def open_settings(self, tab=0):
        self.show()
        if self.settings and self.settings.winfo_exists():
            self.settings.lift()
            self.settings.nb.select(tab)
            return
        self.settings = SettingsDialog(self, tab)

    def apply_config(self, cfg):
        core.save_config(cfg)
        self.config = cfg
        self.monitor.apply_config(cfg)
        self._cats_key = None  # カテゴリ設定が変わったかもしれないので描き直す
        self._apply_window_options()

    def quit(self):
        self.monitor.stop()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 高 DPI 画面でぼやけないように
    except (AttributeError, OSError):
        pass

    mutex = acquire_single_instance()
    if mutex is None:
        messagebox.showinfo("WorkMonitor", "すでに起動しています。タスクトレイのアイコンから開いてください。")
        return
    App(start_minimized="--minimized" in sys.argv).run()


if __name__ == "__main__":
    main()
