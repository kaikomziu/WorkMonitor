"""画面の上に常に表示する小さなタイマー（オーバーレイ）"""

import ctypes
import tkinter as tk

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020   # クリックを後ろのウィンドウに通す
WS_EX_TOOLWINDOW = 0x00000080    # タスクバーや Alt+Tab に出さない
WS_EX_NOACTIVATE = 0x08000000    # クリックしても前面アプリを奪わない（作業判定を邪魔しない）

TRANS = "#010203"  # 透明にする色（角丸の外側）
SCALES = {"小": 0.8, "中": 1.0, "大": 1.35}
PANEL = "#1d2027"
TEXT = "#ffffff"
SUB = "#aab1bd"
TRACK = "#343844"
GOAL = "#7b93ff"
GOAL_DONE = "#22a06b"
MARGIN = 24


class Overlay:
    def __init__(self, root, on_moved, on_open_main, on_open_settings, on_hide):
        self.root = root
        self.on_moved = on_moved
        self.win = None
        self.cfg = {}
        self._drag = None
        self._last = None
        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label="メイン画面を開く", command=on_open_main)
        self.menu.add_command(label="設定を開く", command=on_open_settings)
        self.menu.add_separator()
        self.menu.add_command(label="オーバーレイを閉じる", command=on_hide)
        self._on_open_main = on_open_main

    # ---- 表示・設定 ----
    def apply(self, cfg):
        """設定を反映（表示 / 非表示・透明度・サイズ・クリック透過）"""
        self.cfg = dict(cfg)
        if not cfg.get("enabled"):
            self._destroy()
            return
        if self.win is None:
            self._create()
        self._layout()
        self.win.attributes("-alpha", max(0.2, min(1.0, cfg.get("opacity", 0.85))))
        self._set_click_through(cfg.get("click_through", False))
        self._last = None  # 次の update で必ず描き直す

    def _create(self):
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=TRANS)
        w.attributes("-transparentcolor", TRANS)
        self.canvas = tk.Canvas(w, bg=TRANS, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Double-Button-1>", lambda e: self._on_open_main())
        self.canvas.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        self.win = w

    def _destroy(self):
        if self.win:
            self.win.destroy()
        self.win = None

    def _layout(self):
        dpi = self.root.winfo_fpixels("1i") / 96
        s = SCALES.get(self.cfg.get("size"), 1.0) * dpi
        self.s = s
        self.w = int(230 * s)
        self.h = int((70 if self.cfg.get("show_app", True) else 50) * s)
        x, y = self.cfg.get("x"), self.cfg.get("y")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if x is None or y is None:
            x, y = sw - self.w - int(MARGIN * dpi), int(MARGIN * dpi)   # 初期位置: 右上
        # 画面外に出ていたら戻す（解像度を変えたとき用）
        x = max(0, min(int(x), sw - self.w))
        y = max(0, min(int(y), sh - self.h))
        self.win.geometry(f"{self.w}x{self.h}+{x}+{y}")
        self.canvas.config(width=self.w, height=self.h)

    def _hwnd(self):
        self.win.update_idletasks()
        return int(self.win.wm_frame(), 16)

    def _set_click_through(self, enabled):
        hwnd = self._hwnd()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if enabled:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    # ---- ドラッグで移動 ----
    def _drag_start(self, e):
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag_move(self, e):
        if self._drag:
            self.win.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _drag_end(self, e):
        if self._drag:
            self._drag = None
            self.on_moved(self.win.winfo_x(), self.win.winfo_y())

    # ---- 描画 ----
    def update(self, time_text, dot_color, line2, progress=None):
        """progress は目標の達成率（0〜1）。None なら目標バーを出さない"""
        if self.win is None:
            return
        # 全画面アプリの後ろに隠れないよう、ときどき最前面を掛け直す
        self.win.attributes("-topmost", True)
        if progress is not None:
            progress = round(progress, 3)
        key = (time_text, dot_color, line2, progress)
        if key == self._last:
            return
        self._last = key

        c, s, w, h = self.canvas, self.s, self.w, self.h
        c.delete("all")
        rounded_rect(c, 0, 0, w, h, int(14 * s), fill=PANEL)
        show_app = self.cfg.get("show_app", True)
        cy = int(26 * s) if show_app else h // 2
        r = int(6 * s)
        dx = int(20 * s)
        c.create_oval(dx - r, cy - r, dx + r, cy + r, fill=dot_color, outline="")
        # フォントサイズは負の値 = ピクセル指定（s に DPI 倍率が入っているため）
        c.create_text(int(36 * s), cy, text=time_text, anchor="w", fill=TEXT,
                      font=("Segoe UI", -int(28 * s), "bold"))
        if show_app:
            c.create_text(int(20 * s) - r, int(53 * s), text=line2, anchor="w", fill=SUB,
                          font=("Yu Gothic UI", -int(13 * s)), width=w - int(26 * s))
        # 目標の進み具合（下端の細いバー。達成したら緑）
        if progress is not None:
            x1, x2 = int(14 * s), w - int(14 * s)
            y1, y2 = h - int(7 * s), h - int(4 * s)
            c.create_rectangle(x1, y1, x2, y2, fill=TRACK, outline="")
            color = GOAL_DONE if progress >= 1 else GOAL
            c.create_rectangle(x1, y1, x1 + (x2 - x1) * progress, y2, fill=color, outline="")


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kw)
