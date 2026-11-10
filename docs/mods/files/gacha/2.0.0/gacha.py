"""作業ガチャ

作業30分ごとにガチャチケットが1枚もらえます。引いて図鑑をコンプリートしよう。

1.1.0: 10連ガチャ（SR以上1つ確定）・天井（50回で SSR 確定）・アイテム追加・レア度別のコンプ報酬を追加
2.0.0: ガチャと図鑑を専用画面に。オーブのレア度昇格・爆発・カードめくりなど超派手な演出と効果音を追加。
       10連の確定枠で図鑑の個数が二重に増えることがある不具合を修正
"""

import math
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import messagebox, ttk

try:
    import winsound
except ImportError:          # Windows 以外では音なし
    winsound = None

MOD_INFO = {
    "name": "作業ガチャ",
    "version": "2.0.0",
    "author": "かるわか",
    "description": "作業30分でガチャチケット1枚。N・R・SR・SSR・UR のアイテムを集めて図鑑を埋めましょう。"
                   "引くときは専用画面で超派手な演出つき。10連はSR以上確定、50回で SSR 確定の天井つき。",
    "api": 1,
}

TICKET_SEC = 30 * 60
PITY = 50

# レア度 → (出る確率 %, アイテム)
POOL = {
    "N":   (58, ["🍙 おにぎり", "☕ コーヒー", "📎 クリップ", "✏ えんぴつ", "🧦 くつした", "🍪 クッキー",
                 "📓 ノート", "🧃 ジュース", "🧻 ティッシュ", "🍬 あめ", "📌 画びょう", "🥤 炭酸水"]),
    "R":   (28, ["⌨ キーボード", "🎧 ヘッドホン", "🪴 観葉植物", "🕶 サングラス", "📚 技術書", "🧸 くま",
                 "🖱 マウス", "🕯 アロマキャンドル", "⏰ 目覚まし時計"]),
    "SR":  (11, ["🖥 ウルトラワイドモニター", "🪑 ゲーミングチェア", "🎹 シンセサイザー", "🔭 望遠鏡",
                 "🛋 ふかふかソファ", "🎮 ゲーム機"]),
    "SSR": (2.5, ["👑 集中の王冠", "🐉 締め切りドラゴン", "🌈 虹色のマウス", "🧙 時間の魔法使い"]),
    "UR":  (0.5, ["🌌 無限の集中力", "⏳ 止まった砂時計"]),
}
ORDER = list(POOL)

# ---- 見た目 ----
W, H = 760, 540
FRAME_MS = 25                     # 描画の時間を足すと約25fps
BG = "#05060c"
RCOL = {"N": "#a7b1bf", "R": "#3fa2ff", "SR": "#c46bff", "SSR": "#ffc83d", "UR": "#ff4fd8"}
RNAME = {"N": "ノーマル", "R": "レア", "SR": "スーパーレア", "SSR": "スペシャルスーパーレア", "UR": "ウルトラレア"}
F_EMOJI = "Segoe UI Emoji"
F_JP = "Yu Gothic UI"
F_BIG = "Arial Black"


def rank(rarity):
    return ORDER.index(rarity)


def roll(min_rarity=None):
    """1回引く。min_rarity を指定すると、それ以上のレア度だけから引く"""
    pool = {k: v for k, v in POOL.items() if not min_rarity or rank(k) >= rank(min_rarity)}
    r = random.uniform(0, sum(v[0] for v in pool.values()))
    for rarity, (rate, items) in pool.items():
        if r < rate:
            return rarity, random.choice(items)
        r -= rate
    rarity = list(pool)[-1]
    return rarity, random.choice(pool[rarity][1])


def split_item(item):
    """「🍙 おにぎり」→（絵文字, 名前）"""
    parts = item.split(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("❔", item)


# ---- 高 DPI 対応 ----
# WorkMonitor は高 DPI モードで動くので、画面の拡大率に合わせて大きさを変える。
# 座標は 96dpi のときの数字で書き、ZCanvas が拡大率をかけて描く（文字の pt は Tk が自動で合わせる）
S = 1.0


class ZCanvas(tk.Canvas):
    """座標と線の太さに拡大率 S をかけるキャンバス"""

    @staticmethod
    def _z(args):
        return [a * S for a in args]

    @staticmethod
    def _kw(kw):
        if "width" in kw:
            kw["width"] = max(1, kw["width"] * S)
        return kw

    def create_rectangle(self, *a, **kw):
        return super().create_rectangle(*self._z(a), **self._kw(kw))

    def create_oval(self, *a, **kw):
        return super().create_oval(*self._z(a), **self._kw(kw))

    def create_line(self, *a, **kw):
        return super().create_line(*self._z(a), **self._kw(kw))

    def create_polygon(self, *a, **kw):
        return super().create_polygon(*self._z(a), **self._kw(kw))

    def create_text(self, *a, **kw):
        return super().create_text(*self._z(a), **self._kw(kw))

    def coords(self, item, *a):
        if a:
            return super().coords(item, *self._z(a))
        return [v / S for v in super().coords(item)]

    def itemconfigure(self, item, **kw):
        return super().itemconfigure(item, **self._kw(kw))


# ---- 色の計算 ----
def _rgb(c):
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def mix(a, b, t):
    """色 a から b へ t（0〜1）だけ近づけた色"""
    t = max(0.0, min(1.0, t))
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))


def hsv(h, s=1.0, v=1.0):
    h = (h % 1.0) * 6
    i = int(h)
    f = h - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def ease_out_back(p):
    c1 = 1.70158
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_out(p):
    return 1 - (1 - max(0.0, min(1.0, p))) ** 3


# ---- 効果音（別スレッドで Beep を鳴らす） ----
class Sound:
    def __init__(self, enabled):
        self.enabled = enabled
        self.seq = []
        self.lock = threading.Lock()
        self.ev = threading.Event()
        self.alive = True
        if winsound:
            threading.Thread(target=self._run, daemon=True).start()

    def play(self, notes, replace=False):
        """notes は [(周波数, ミリ秒), ...]。周波数 0 は休み"""
        if not (self.enabled and winsound):
            return
        with self.lock:
            if replace:
                self.seq = []
            self.seq.extend(notes)
        self.ev.set()

    def stop(self):
        with self.lock:
            self.seq = []

    def close(self):
        self.alive = False
        self.stop()
        self.ev.set()

    def _run(self):
        while self.alive:
            self.ev.wait(0.5)
            while self.alive:
                with self.lock:
                    if not self.seq:
                        self.ev.clear()
                        break
                    freq, ms = self.seq.pop(0)
                try:
                    if freq <= 0:
                        time.sleep(ms / 1000)
                    else:
                        winsound.Beep(max(37, min(32767, int(freq))), int(ms))
                except Exception:
                    time.sleep(ms / 1000)


SE_RISE = [(880, 45), (1175, 45), (1568, 70)]
SE_FLIP = [(1320, 25)]
SE_FANFARE = {
    "N":   [(523, 90), (659, 160)],
    "R":   [(523, 70), (659, 70), (784, 180)],
    "SR":  [(523, 70), (659, 70), (784, 70), (1047, 240)],
    "SSR": [(784, 80), (988, 80), (1175, 80), (1568, 120), (0, 40), (1568, 80), (1976, 320)],
    "UR":  [(523, 60), (659, 60), (784, 60), (1047, 60), (1319, 60), (1568, 60), (2093, 140), (0, 50),
            (2093, 60), (2637, 60), (3136, 420)],
}


# ---- カードの絵 ----
def draw_card(cv, tag, cx, cy, w, h, face, rarity=None, item=None, new=False, big=False,
              back_glow=None, show_text=True):
    cv.delete(tag)
    w = max(2.0, w)
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    if not face:
        oc = back_glow or "#4a5578"
        if back_glow:
            for pad, t in ((12, 0.75), (7, 0.5), (3, 0.25)):
                cv.create_rectangle(x0 - pad, y0 - pad, x1 + pad, y1 + pad, outline=mix(oc, BG, t), width=3,
                                    tags=(tag,))
        cv.create_rectangle(x0, y0, x1, y1, fill="#151a2c", outline=oc, width=3, tags=(tag,))
        if w > 30:
            cv.create_rectangle(x0 + 8, y0 + 8, x1 - 8, y1 - 8, outline="#28304e", width=2, tags=(tag,))
            cv.create_line(x0 + 8, y0 + 8, x1 - 8, y1 - 8, fill="#1f2640", width=2, tags=(tag,))
            cv.create_line(x1 - 8, y0 + 8, x0 + 8, y1 - 8, fill="#1f2640", width=2, tags=(tag,))
            cv.create_text(cx, cy, text="?", fill=oc, font=(F_BIG, 46 if big else 30), tags=(tag,))
        return
    col = RCOL[rarity]
    glow_tags = (tag, "urglow") if rarity == "UR" else (tag, "glow_" + rarity)
    for pad, t in ((14, 0.78), (9, 0.55), (4, 0.25)):
        cv.create_rectangle(x0 - pad, y0 - pad, x1 + pad, y1 + pad, outline=mix(col, BG, t), width=3,
                            tags=glow_tags)
    cv.create_rectangle(x0, y0, x1, y1, fill=mix(col, "#0a0c16", 0.8), outline=col, width=3, tags=glow_tags)
    band = h * 0.15
    cv.create_rectangle(x0, y0, x1, y0 + band, fill=col, outline=col, tags=glow_tags)
    if not show_text or w < h * 0.45:
        return
    emo, name = split_item(item)
    cv.create_text(cx, y0 + band / 2, text=rarity, fill="#0b0d16", font=(F_BIG, 26 if big else 14), tags=(tag,))
    cv.create_text(cx, y0 + band + (20 if big else 12), text="★" * (rank(rarity) + 1), fill=col,
                   font=(F_JP, 16 if big else 9, "bold"), tags=(tag,))
    cv.create_text(cx, cy + (2 if big else 0), text=emo, fill="white", font=(F_EMOJI, 78 if big else 34),
                   tags=(tag,))
    cv.create_text(cx, y1 - h * 0.13, text=name, fill="white", width=w - 14, justify="center",
                   font=(F_JP, 17 if big else 9, "bold"), tags=(tag,))
    if new:
        bw, bh = (64, 26) if big else (40, 17)
        cv.create_rectangle(x1 - bw + 6, y0 - bh / 2, x1 + 6, y0 + bh / 2, fill="#ff2d55", outline="white",
                            width=2, tags=(tag,))
        cv.create_text(x1 - bw / 2 + 6, y0, text="NEW", fill="white", font=(F_BIG, 12 if big else 8),
                       tags=(tag,))


# ---- ガチャ演出の画面 ----
class GachaShow:
    """results: [(rarity, item, new), ...]。mode は "pull"（引く）か "view"（図鑑から見る）"""

    def __init__(self, api, results, sound, mode="pull", on_again=None, on_book=None, on_close=None,
                 count=None):
        self.api, self.results, self.sound, self.mode = api, results, sound, mode
        self.on_again, self.on_book, self.on_close = on_again, on_book, on_close
        self.count = count
        self.dead = False
        self.best = max(results, key=lambda r: rank(r[0]))[0]
        self.bi = rank(self.best)
        self.ten = len(results) > 1

        self.top = tk.Toplevel(api.root)
        self.top.title("作業ガチャ" if mode == "pull" else "作業ガチャ - 図鑑")
        self.top.configure(bg="black")
        self.top.resizable(False, False)
        sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        ww, wh = int(W * S), int(H * S)
        self.top.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{max(0, (sh - wh) // 2 - int(30 * S))}")
        self.box = tk.Frame(self.top, width=ww, height=wh, bg="black")
        self.box.pack(fill="both", expand=True)
        self.cv = ZCanvas(self.box, width=ww, height=wh, bg=BG, highlightthickness=0)
        self.cv.place(x=0, y=0)
        self.cv.bind("<Button-1>", self.on_click)
        self.top.bind("<space>", self.on_click)
        self.top.bind("<Return>", self.on_click)
        self.top.bind("<Escape>", lambda e: self.close())
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.lift()
        self.top.focus_force()

        self.t = 0
        self.phase = None
        self.parts = []        # パーティクル
        self.flashes = []      # 画面全体の光
        self.rings = []        # 衝撃波
        self.pops = []         # 飛び出す文字
        self.rays = []         # 後ろで回る光線
        self.shake = 0.0
        self.warp = 1.0
        self.cx, self.cy = W / 2, H / 2 - 10
        self.make_stars()
        if mode == "view":
            self.start_burst()
        else:
            self.start_charge()
        self.api.after(FRAME_MS, self.step)

    # -- 共通 --
    def alive(self):
        try:
            return not self.dead and self.top.winfo_exists()
        except tk.TclError:
            return False

    def close(self):
        if self.dead:
            return
        self.dead = True
        self.sound.stop()
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        if self.on_close:
            self.on_close(self)

    def step(self):
        if not self.alive():
            return
        try:
            self.t += 1
            self.update_stars()
            getter = {"charge": self.step_charge, "burst": self.step_burst,
                      "single": self.step_single, "ten": self.step_ten, "done": self.step_done}
            getter[self.phase]()
            self.update_rays()
            self.update_rings()
            self.update_parts()
            self.update_pops()
            self.update_flashes()
            self.update_shake()
        except tk.TclError:
            self.dead = True
            return
        self.api.after(FRAME_MS, self.step)

    def on_click(self, event=None):
        if self.phase in ("charge", "burst"):
            self.sound.stop()
            self.cv.delete("orb", "charge")
            self.start_reveal(skipped=True)
        elif self.phase == "ten":
            self.skip_flips()

    # -- 背景の星（ワープ線） --
    def make_stars(self):
        self.stars = []
        for _ in range(110):
            a = random.uniform(0, math.tau)
            d = random.uniform(10, 480)
            sid = self.cv.create_line(0, 0, 0, 0, fill="#3a4466", width=1, tags=("bg",))
            self.stars.append([a, d, random.uniform(0.6, 1.6), sid])

    def update_stars(self):
        for s in self.stars:
            a, d, sp, sid = s
            d += sp * self.warp * (1 + d / 120)
            if d > 520:
                d = random.uniform(5, 60)
                a = random.uniform(0, math.tau)
                s[0] = a
            s[1] = d
            ln = sp * self.warp * 3 + 2
            ca, sa = math.cos(a), math.sin(a)
            self.cv.coords(sid, self.cx + ca * d, self.cy + sa * d, self.cx + ca * (d + ln), self.cy + sa * (d + ln))
            br = min(1.0, d / 400) * min(1.0, 0.35 + self.warp / 10)
            self.cv.itemconfigure(sid, fill=mix(BG, self.star_col(), br), width=1 if self.warp < 6 else 2)

    def star_col(self):
        if self.phase in ("charge",):
            return self.orb_col
        if self.bi >= 4:
            return hsv(self.t / 40)
        return mix(RCOL[self.best], "#ffffff", 0.4)

    # -- チャージ（オーブがたまってレア度が上がっていく） --
    def start_charge(self):
        self.phase = "charge"
        self.ct = 0
        self.clen = 40 + 12 * self.bi
        # 昇格の段階: 白 → R → … → いちばん良いレア度
        self.stages = [("N", "#ffffff")] + [(r, RCOL[r]) for r in ORDER[1:self.bi + 1]]
        n = len(self.stages) - 1
        self.up_at = [int(self.clen * (0.3 + 0.55 * (k + 1) / n)) for k in range(n)] if n else []
        self.stage = 0
        self.orb_col = "#ffffff"
        self.orb = [self.cv.create_oval(0, 0, 0, 0, outline="", fill=BG, tags=("orb",)) for _ in range(4)]
        self.cv.create_text(W / 2, H - 22, text="クリックでスキップ", fill="#5b6588", font=(F_JP, 10),
                            tags=("charge",))
        self.sound.play([(330, 40), (0, 30), (392, 40), (0, 30), (440, 40)], replace=True)

    def step_charge(self):
        self.ct += 1
        p = self.ct / self.clen
        self.warp = 1 + 14 * p ** 2
        # 昇格
        if self.stage < len(self.up_at) and self.ct >= self.up_at[self.stage]:
            self.stage += 1
            r, col = self.stages[self.stage]
            self.orb_col = col
            self.shake = 6 + 5 * self.stage
            self.flash(col, 7, 0.35)
            self.ring(self.cx, self.cy, col, speed=16, width=10)
            self.burst_parts(self.cx, self.cy, col, 40, speed=9)
            msg = {1: "!", 2: "!!", 3: "!!!", 4: "！？！？"}.get(self.stage, "!")
            if r == "UR":
                msg = "！？！？！？"
            self.pop(msg, col, size=(54 + 8 * self.stage) if len(msg) <= 3 else 44, y=self.cy - 150, life=18)
            self.sound.play([(f * (1 + 0.12 * self.stage), ms) for f, ms in SE_RISE], replace=True)
        col = self.orb_col if self.orb_col != "#ffffff" or self.bi < 4 else self.orb_col
        if self.stages[self.stage][0] == "UR":
            col = hsv(self.t / 14)
            self.orb_col = col
            self.shake = max(self.shake, 4)
        # 吸い込まれる粒
        for _ in range(3 + int(6 * p)):
            a = random.uniform(0, math.tau)
            d = random.uniform(260, 380)
            sp = random.uniform(6, 12) * (1 + p)
            x, y = self.cx + math.cos(a) * d, self.cy + math.sin(a) * d
            self.add_part(x, y, -math.cos(a) * sp, -math.sin(a) * sp, mix(col, "#ffffff", random.random() * 0.5),
                          life=int(d / sp), size=random.uniform(1.5, 3.5), inward=True)
        # 集まる輪
        if self.ct % max(4, 12 - int(8 * p)) == 0:
            self.ring(self.cx, self.cy, col, speed=-14, width=3, r0=300)
        # オーブ本体
        if self.ct > self.clen - 8:                      # 最後にぎゅっと縮む
            r = 60 * (self.clen - self.ct) / 8 + 3
        else:
            r = 16 + 44 * p + math.sin(self.ct * 0.6) * (3 + 6 * p)
        for k, oid in enumerate(self.orb):
            rr = r * (1 + 0.45 * (3 - k))
            c = mix(col, BG, 0.25 + 0.22 * (3 - k)) if k < 3 else mix(col, "#ffffff", 0.6)
            self.cv.coords(oid, self.cx - rr, self.cy - rr, self.cx + rr, self.cy + rr)
            self.cv.itemconfigure(oid, fill=c)
        self.cv.tag_raise("orb")
        if self.ct % 6 == 0:
            self.sound.play([(400 + 900 * p, 22)])
        if self.ct >= self.clen:
            self.cv.delete("orb", "charge")
            self.start_burst()

    # -- 爆発 --
    def start_burst(self):
        self.phase = "burst"
        self.bt = 0
        col = RCOL[self.best]
        big = self.mode == "pull"
        self.warp = 9 if big else 3
        self.flash("#ffffff", 12 if big else 6, top=True)
        self.shake = (14 + 8 * self.bi) if big else 4
        self.make_rays(col)
        n = (60 + 50 * self.bi) if big else 50
        self.burst_parts(self.cx, self.cy, col, n, speed=14 + 3 * self.bi, gravity=0.18)
        self.burst_parts(self.cx, self.cy, "#ffffff", n // 3, speed=10)
        for k in range(3 if big else 1):
            self.ring(self.cx, self.cy, col if k else "#ffffff", speed=22 - 4 * k, width=14 - 3 * k, delay=k * 3)
        self.sound.play([(150, 40), (110, 60)] + SE_FANFARE[self.best], replace=True)
        if self.bi >= 3 and big and not self.ten:
            label = {"SSR": "SSR 確定!!", "UR": "ULTRA RARE"}[self.best]
            self.pop(label, col, size=40, y=self.cy - 150, life=26, grow=True)

    def step_burst(self):
        self.bt += 1
        self.warp = max(1.0, self.warp * 0.9)
        if self.bt >= (16 if self.mode == "pull" else 6):
            self.start_reveal()

    # -- 後ろで回る光線 --
    def make_rays(self, col):
        self.cv.delete("ray")
        self.rays = []
        n = 6 + 3 * self.bi
        for i in range(n * 2):
            c = mix(col, BG, 0.55 if i % 2 == 0 else 0.8)
            rid = self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill=c, outline="", tags=("ray",))
            self.rays.append((i, rid))
        self.ray_n = n * 2
        self.ray_rot = 0.0
        self.cv.tag_lower("ray")
        self.cv.tag_lower("bg")

    def update_rays(self):
        if not self.rays:
            return
        spd = 0.08 if self.phase == "burst" else 0.012
        self.ray_rot += spd
        half = math.pi / self.ray_n * 0.55
        R = 700
        for i, rid in self.rays:
            a = self.ray_rot + math.tau * i / self.ray_n
            self.cv.coords(rid, self.cx, self.cy,
                           self.cx + math.cos(a - half) * R, self.cy + math.sin(a - half) * R,
                           self.cx + math.cos(a + half) * R, self.cy + math.sin(a + half) * R)
            if self.bi >= 4:
                self.cv.itemconfigure(rid, fill=mix(hsv(self.t / 50 + i / self.ray_n), BG,
                                                    0.55 if i % 2 == 0 else 0.78))

    # -- 結果の発表 --
    def start_reveal(self, skipped=False):
        self.warp = 0.8
        if not self.rays:
            self.make_rays(RCOL[self.best])
        if self.ten:
            self.phase = "ten"
            self.setup_ten(skipped)
        else:
            self.phase = "single"
            self.st = 0
            if skipped:
                self.flash("#ffffff", 8)
                self.sound.play(SE_FANFARE[self.best], replace=True)

    # 1枚
    def step_single(self):
        self.st += 1
        r, item, new = self.results[0]
        col = RCOL[r]
        p = min(1.0, self.st / 12)
        s = max(0.05, ease_out_back(p))
        cw, ch = 250, 330
        draw_card(self.cv, "card", self.cx, self.cy + 22, cw * s, ch * s, True, r, item, new, big=True,
                  show_text=p >= 1)
        if self.st == 12:
            self.shake = max(self.shake, 6 + 3 * rank(r))
            self.burst_parts(self.cx, self.cy + 22, col, 30 + 15 * rank(r), speed=8)
        # レア度の文字が上から落ちてくる
        if self.st == 13:
            self.letters = []
            text = r if len(r) <= 3 else r
            gap = 46
            x0 = self.cx - gap * (len(text) - 1) / 2
            for k, ch_ in enumerate(text):
                lid = self.cv.create_text(x0 + gap * k, -60, text=ch_, fill=col, font=(F_BIG, 44),
                                          tags=("letters",))
                sid = self.cv.create_text(x0 + gap * k + 3, -57, text=ch_, fill="#000000", font=(F_BIG, 44),
                                          tags=("letters",))
                self.cv.tag_lower(sid, lid)
                self.letters.append((lid, sid, k))
        if self.st >= 13:
            for lid, sid, k in self.letters:
                q = (self.st - 13 - k * 3) / 8
                y = -60 + (44 - -60) * ease_out_back(max(0.0, min(1.0, q))) if q > 0 else -60
                x = self.cv.coords(lid)[0]
                self.cv.coords(lid, x, y)
                self.cv.coords(sid, x + 3, y + 3)
                if self.bi >= 4:
                    self.cv.itemconfigure(lid, fill=hsv(self.t / 20 + k * 0.15))
                if 0 < q <= 1 / 8 + 0.001:
                    self.sound.play([(900 + 200 * k, 30)])
        if self.st == 22 and new:
            self.stamp("NEW!!", self.cx + 150, self.cy - 120)
        if self.st >= 26:
            self.cv.tag_raise("letters")
            self.finish()
        self.extra_fx(r)

    # 10連
    def setup_ten(self, skipped):
        self.tt = 0
        cw, ch, gap = 116, 166, 18
        x0 = (W - (cw * 5 + gap * 4)) / 2 + cw / 2
        self.slots = []
        cur = 4 if skipped else 22
        for i, (r, item, new) in enumerate(self.results):
            x = x0 + (i % 5) * (cw + gap)
            y = 152 + (i // 5) * 196
            pre = 16 if rank(r) >= 3 else (6 if rank(r) == 2 else 0)
            start = cur + pre
            self.slots.append({"x": x, "y": y, "r": r, "item": item, "new": new, "deal": i * 2,
                               "pre": pre, "start": start, "hit": False, "w": cw, "h": ch, "last": None})
            cur = start + (8 if rank(r) >= 2 else 5)
        self.ten_end = cur + 10
        self.cv.create_text(W / 2, 40, text="10連ガチャ", fill="#c9d1ea", font=(F_JP, 18, "bold"),
                            tags=("tenhead",))
        self.cv.create_text(W / 2, H - 22, text="クリックで全部めくる", fill="#5b6588", font=(F_JP, 10),
                            tags=("tenhint",))
        if skipped:
            self.flash("#ffffff", 6)

    def skip_flips(self):
        for s in self.slots:
            if not s["hit"]:
                s["start"] = self.tt - 20
                s["pre"] = 0
                s["deal"] = -100
        self.ten_end = self.tt + 4
        self.sound.play(SE_FANFARE[self.best], replace=True)
        self.flash("#ffffff", 6)

    def step_ten(self):
        self.tt += 1
        for i, s in enumerate(self.slots):
            dp = (self.tt - s["deal"]) / 8
            if dp <= 0:
                continue
            e = ease_out(dp)
            x = self.cx + (s["x"] - self.cx) * e
            y = H + 120 + (s["y"] - H - 120) * e
            fp = (self.tt - s["start"]) / 8
            tag = f"c{i}"
            if fp < 0:
                # めくる前。いいカードはここで光って震える（ため）
                glow = None
                if self.tt >= s["start"] - s["pre"] and s["pre"]:
                    k = (self.tt - (s["start"] - s["pre"])) / s["pre"]
                    col = RCOL[s["r"]] if k > 0.4 else "#ffffff"
                    if s["r"] == "UR" and k > 0.4:
                        col = hsv(self.t / 6)
                    glow = mix("#4a5578", col, 0.5 + 0.5 * math.sin(self.t * 1.3))
                    x += random.uniform(-1, 1) * 4 * k
                    y += random.uniform(-1, 1) * 4 * k
                    if self.tt % 3 == 0:
                        self.sound.play([(500 + 700 * k, 18)])
                key = ("back", round(x), round(y), glow)
                if key != s["last"]:
                    draw_card(self.cv, tag, x, y, s["w"], s["h"], False, back_glow=glow)
                    s["last"] = key
            elif fp < 1:
                sx = abs(1 - 2 * fp)
                face = fp >= 0.5
                draw_card(self.cv, tag, x, y, s["w"] * sx, s["h"], face, s["r"], s["item"], s["new"],
                          show_text=False)
                s["last"] = None
                if face and not s["hit"]:
                    s["hit"] = True
                    self.on_card_open(s)
            else:
                if not s["hit"]:
                    s["hit"] = True
                    self.on_card_open(s, quiet=True)
                key = ("face",)
                if s["last"] != key:
                    draw_card(self.cv, tag, s["x"], s["y"], s["w"], s["h"], True, s["r"], s["item"], s["new"])
                    s["last"] = key
        if self.tt >= self.ten_end:
            self.cv.delete("tenhint")
            new_n = sum(1 for _, _, nw in self.results if nw)
            summ = f"最高 {self.best}" + (f"   ·   NEW × {new_n}" if new_n else "")
            self.cv.itemconfigure("tenhead", text=summ, fill=RCOL[self.best])
            self.finish()
        self.extra_fx(self.best, light=True)

    def on_card_open(self, s, quiet=False):
        ri = rank(s["r"])
        col = RCOL[s["r"]]
        if quiet:
            return
        self.burst_parts(s["x"], s["y"], col, 10 + 12 * ri, speed=4 + 2 * ri, gravity=0.15)
        if ri >= 2:
            self.ring(s["x"], s["y"], col, speed=10 + 2 * ri, width=6)
        if ri >= 3:
            self.flash(col if ri == 3 else "#ffffff", 8, 0.55)
            self.shake = 10 + 6 * (ri - 3)
            self.pop(s["r"] + "!!", col, size=40, y=s["y"] - 100, x=s["x"], life=16)
            self.sound.play(SE_FANFARE[s["r"]][-4:])
        elif ri == 2:
            self.sound.play([(1047, 40), (1568, 70)])
        else:
            self.sound.play(SE_FLIP if ri == 0 else [(1175, 30), (1568, 30)])

    # 両方共通の後の演出
    def extra_fx(self, r, light=False):
        ri = rank(r)
        if ri >= 3:                                       # 紙吹雪
            for _ in range(2 if light else 3):
                c = hsv(random.random()) if ri >= 4 else random.choice([RCOL["SSR"], "#ffffff", "#ffe9a8"])
                self.add_part(random.uniform(0, W), -10, random.uniform(-1, 1), random.uniform(2, 4), c,
                              life=160, size=random.uniform(3, 6), conf=True)
        elif ri == 2 and self.t % 2 == 0:                 # きらきら
            a = random.uniform(0, math.tau)
            d = random.uniform(140, 300)
            self.add_part(self.cx + math.cos(a) * d, self.cy + math.sin(a) * d * 0.7, 0, -0.6, RCOL["SR"],
                          life=24, size=2.5)
        if ri >= 4 and self.t % 3 == 0:
            self.cv.itemconfigure("urglow", outline=hsv(self.t / 30))

    def finish(self):
        self.phase = "done"
        self.dt = 0
        bw, bh, y = 150, 40, H - 40
        tickets = self.api.data.get("tickets", 0)
        if self.mode == "view":
            n = self.count or 0
            self.cv.create_text(W / 2, H - 82, text=f"所持数 × {n}   ·   {RNAME[self.best]}", fill="#c9d1ea",
                                font=(F_JP, 12, "bold"), tags=("ui",))
            buttons = [("閉じる", self.close, True)]
        else:
            buttons = [(f"もう1回  🎟1", lambda: self.again(1), tickets >= 1),
                       (f"10連  🎟10", lambda: self.again(10), tickets >= 10),
                       ("📖 図鑑", self.book, True),
                       ("閉じる", self.close, True)]
            self.cv.create_text(W - 16, 18, text=f"🎟 {tickets} 枚", fill="#c9d1ea", anchor="e",
                                font=(F_JP, 11, "bold"), tags=("ui",))
        total = len(buttons) * bw + (len(buttons) - 1) * 14
        x = (W - total) / 2
        for i, (label, func, ok) in enumerate(buttons):
            self.button(x, y - bh / 2, bw, bh, label, func, ok, f"btn{i}")
            x += bw + 14

    def button(self, x, y, w, h, label, func, ok, tag):
        fill = "#1d2440" if ok else "#11141f"
        oc = "#5a6aa8" if ok else "#262b3d"
        tc = "#ffffff" if ok else "#4a5070"
        self.cv.create_rectangle(x, y, x + w, y + h, fill=fill, outline=oc, width=2, tags=(tag, "ui", tag + "r"))
        self.cv.create_text(x + w / 2, y + h / 2, text=label, fill=tc, font=(F_JP, 11, "bold"), tags=(tag, "ui"))
        if ok:
            self.cv.tag_bind(tag, "<Button-1>", lambda e: func())
            self.cv.tag_bind(tag, "<Enter>", lambda e: self.cv.itemconfigure(tag + "r", fill="#2d3a6e",
                                                                             outline="#9fb0ff"))
            self.cv.tag_bind(tag, "<Leave>", lambda e: self.cv.itemconfigure(tag + "r", fill=fill, outline=oc))

    def step_done(self):
        self.dt += 1
        self.extra_fx(self.best, light=self.ten)
        self.cv.tag_raise("ui")

    def again(self, n):
        if self.on_again:
            self.on_again(n)

    def book(self):
        if self.on_book:
            self.on_book()

    # -- 効果の部品 --
    def add_part(self, x, y, vx, vy, col, life=30, size=3.0, gravity=0.0, inward=False, conf=False):
        if len(self.parts) > 520:
            return
        if conf:
            pid = self.cv.create_rectangle(x, y, x + size, y + size * 1.6, fill=col, outline="", tags=("fx",))
        else:
            pid = self.cv.create_oval(x - size, y - size, x + size, y + size, fill=col, outline="", tags=("fx",))
        self.parts.append({"id": pid, "x": x, "y": y, "vx": vx, "vy": vy, "life": life, "max": life,
                           "size": size, "g": gravity, "col": col, "in": inward, "conf": conf,
                           "ph": random.uniform(0, math.tau)})

    def burst_parts(self, x, y, col, n, speed=8.0, gravity=0.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.3, 1.0) * speed
            c = mix(col, "#ffffff", random.random() * 0.6)
            self.add_part(x, y, math.cos(a) * sp, math.sin(a) * sp, c, life=random.randint(18, 40),
                          size=random.uniform(2, 4.5), gravity=gravity)

    def update_parts(self):
        keep = []
        for p in self.parts:
            p["life"] -= 1
            if p["conf"]:
                p["x"] += p["vx"] + math.sin(self.t * 0.2 + p["ph"]) * 1.5
                p["y"] += p["vy"]
            else:
                p["vy"] += p["g"]
                if not p["in"]:
                    p["vx"] *= 0.97
                    p["vy"] *= 0.97
                p["x"] += p["vx"]
                p["y"] += p["vy"]
            if p["life"] <= 0 or p["y"] > H + 20 or (p["in"] and math.hypot(p["x"] - self.cx, p["y"] - self.cy) < 20):
                self.cv.delete(p["id"])
                continue
            s = p["size"]
            if p["conf"]:
                w = s * abs(math.cos(self.t * 0.25 + p["ph"])) + 1
                self.cv.coords(p["id"], p["x"] - w, p["y"], p["x"] + w, p["y"] + s * 1.6)
            else:
                if p["life"] < 10 and not p["in"]:
                    s *= p["life"] / 10
                self.cv.coords(p["id"], p["x"] - s, p["y"] - s, p["x"] + s, p["y"] + s)
            keep.append(p)
        self.parts = keep
        self.cv.tag_raise("fx")

    def ring(self, x, y, col, speed=16.0, width=8.0, delay=0, r0=4.0):
        rid = self.cv.create_oval(x, y, x, y, outline="", width=width, tags=("ring",))
        self.rings.append({"id": rid, "x": x, "y": y, "r": r0, "sp": speed, "w": width, "col": col,
                           "delay": delay, "age": 0})

    def update_rings(self):
        keep = []
        for g in self.rings:
            if g["delay"] > 0:
                g["delay"] -= 1
                keep.append(g)
                continue
            g["age"] += 1
            g["r"] += g["sp"]
            life = 18 if g["sp"] > 0 else 300 / abs(g["sp"])
            k = g["age"] / life
            if k >= 1 or g["r"] < 2:
                self.cv.delete(g["id"])
                continue
            r = g["r"]
            self.cv.coords(g["id"], g["x"] - r, g["y"] - r, g["x"] + r, g["y"] + r)
            c = mix(g["col"], BG, k) if g["sp"] > 0 else mix(BG, g["col"], k)
            self.cv.itemconfigure(g["id"], outline=c, width=max(1, g["w"] * (1 - k) if g["sp"] > 0 else g["w"]))
            keep.append(g)
        self.rings = keep

    def flash(self, col, frames, strength=1.0, top=False):
        """画面を光らせる。top=False のときは背景の光線のすぐ上（カードやオーブの下）に置く"""
        fid = self.cv.create_rectangle(-20, -20, W + 20, H + 20, fill=mix(BG, col, strength), outline="",
                                       tags=("flash",))
        if not top:
            self.cv.tag_raise(fid, "ray" if self.rays else "bg")
        self.flashes.append({"id": fid, "col": col, "n": frames, "age": 0, "s": strength, "top": top})

    def update_flashes(self):
        keep = []
        for f in self.flashes:
            f["age"] += 1
            if f["age"] >= f["n"]:
                self.cv.delete(f["id"])
                continue
            k = f["age"] / f["n"]
            self.cv.itemconfigure(f["id"], fill=mix(f["col"], BG, 1 - f["s"] * (1 - k) ** 2))
            if f["top"]:
                self.cv.tag_raise(f["id"])
            keep.append(f)
        self.flashes = keep

    def pop(self, text, col, size=48, y=None, x=None, life=20, grow=False):
        x = self.cx if x is None else x
        y = self.cy if y is None else y
        sid = self.cv.create_text(x + 3, y + 3, text=text, fill="#000000", font=(F_BIG, size), tags=("pop",))
        tid = self.cv.create_text(x, y, text=text, fill=col, font=(F_BIG, size), tags=("pop",))
        self.pops.append({"t": tid, "s": sid, "age": 0, "life": life, "size": size, "col": col, "grow": grow,
                          "y": y, "x": x, "stamp": False})

    def stamp(self, text, x, y):
        sid = self.cv.create_text(x + 3, y + 3, text=text, fill="#000000", font=(F_BIG, 80), angle=18,
                                  tags=("pop",))
        tid = self.cv.create_text(x, y, text=text, fill="#ff2d55", font=(F_BIG, 80), angle=18, tags=("pop",))
        self.pops.append({"t": tid, "s": sid, "age": 0, "life": 10 ** 9, "size": 30, "col": "#ff2d55",
                          "grow": False, "y": y, "x": x, "stamp": True})
        self.sound.play([(1568, 40), (2093, 80)])

    def update_pops(self):
        keep = []
        for p in self.pops:
            p["age"] += 1
            k = p["age"] / p["life"]
            if k >= 1:
                self.cv.delete(p["t"], p["s"])
                continue
            if p["stamp"]:
                if p["age"] <= 6:
                    sz = int(80 - (80 - p["size"]) * p["age"] / 6)
                    for i in (p["t"], p["s"]):
                        self.cv.itemconfigure(i, font=(F_BIG, sz))
                    if p["age"] == 6:
                        self.shake = max(self.shake, 7)
                        self.burst_parts(p["x"], p["y"], "#ff2d55", 18, speed=6)
                else:
                    self.cv.itemconfigure(p["t"], fill="#ff2d55" if (p["age"] // 6) % 2 else "#ffd23f")
            else:
                sz = int(p["size"] * ((0.7 + 0.4 * ease_out(k * 2)) if p["grow"] else (1.3 - 0.3 * min(1, k * 4))))
                col = hsv(self.t / 10) if p["col"] == RCOL["UR"] else p["col"]
                fade = max(0.0, (k - 0.6) / 0.4)
                dy = -20 * k
                self.cv.itemconfigure(p["t"], font=(F_BIG, max(8, sz)), fill=mix(col, BG, fade))
                self.cv.itemconfigure(p["s"], font=(F_BIG, max(8, sz)), fill=mix("#000000", BG, fade))
                self.cv.coords(p["t"], p["x"], p["y"] + dy)
                self.cv.coords(p["s"], p["x"] + 3, p["y"] + dy + 3)
            self.cv.tag_raise(p["s"])
            self.cv.tag_raise(p["t"])
            keep.append(p)
        self.pops = keep

    def update_shake(self):
        if self.shake > 0.5:
            dx = random.uniform(-1, 1) * self.shake * S
            dy = random.uniform(-1, 1) * self.shake * S
            self.cv.place(x=dx, y=dy)
            self.shake *= 0.82
        elif self.shake:
            self.shake = 0
            self.cv.place(x=0, y=0)


# ---- 図鑑の画面 ----
class Book:
    BW, BH = 820, 640

    def __init__(self, api, open_item, on_close):
        self.api, self.open_item, self.on_close = api, open_item, on_close
        self.dead = False
        self.t = 0
        self.top = tk.Toplevel(api.root)
        self.top.title("作業ガチャ - 図鑑")
        self.top.configure(bg=BG)
        self.top.geometry(f"{int(self.BW * S)}x{int(self.BH * S)}")
        self.top.minsize(int(600 * S), int(400 * S))
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.bind("<Escape>", lambda e: self.close())

        self.head = ZCanvas(self.top, height=int(112 * S), bg=BG, highlightthickness=0)
        self.head.pack(fill="x")
        body = tk.Frame(self.top, bg=BG)
        body.pack(fill="both", expand=True)
        self.cv = ZCanvas(body, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.top.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(int(-e.delta / 120) * 3, "units"))
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.width = 0
        self.hover = None
        self.top.lift()
        self.top.focus_force()
        self.draw_head()
        self.api.after(FRAME_MS, self.step)

    def alive(self):
        try:
            return not self.dead and self.top.winfo_exists()
        except tk.TclError:
            return False

    def close(self):
        if self.dead:
            return
        self.dead = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        if self.on_close:
            self.on_close(self)

    def refresh(self):
        if self.alive():
            self.draw_head()
            self.width = 0
            self.draw()

    def draw_head(self):
        h = self.head
        h.delete("all")
        owned = self.api.data["owned"]
        total = sum(len(v[1]) for v in POOL.values())
        got = sum(1 for v in POOL.values() for it in v[1] if it in owned)
        self.ratio = got / total if total else 0
        h.create_text(24, 30, text="📖  ガチャ図鑑", anchor="w", fill="white", font=(F_JP, 20, "bold"))
        h.create_text(24, 62, text=f"{got} / {total} 種類   ·   合計 {self.api.data['pulls']} 回   ·   "
                                   f"🎟 {self.api.data['tickets']} 枚   ·   天井まで {PITY - self.api.data['pity']} 回",
                      anchor="w", fill="#9aa4c4", font=(F_JP, 11))
        h.create_rectangle(24, 82, 24 + 400, 98, fill="#141828", outline="#2a3150", tags=("barbg",))
        h.create_rectangle(24, 82, 24, 98, fill=RCOL["SSR"], outline="", tags=("bar",))
        h.create_text(434, 90, text=f"{int(self.ratio * 100)}%", anchor="w", fill="white",
                      font=(F_BIG, 11), tags=("pct",))
        x = 500
        for r in ORDER:
            done = r in self.api.data["complete"]
            col = RCOL[r] if done else "#2a3150"
            h.create_rectangle(x, 80, x + 54, 100, fill=mix(col, BG, 0.6) if done else BG, outline=col, width=2)
            h.create_text(x + 27, 90, text=("👑" if done else "") + r, fill="white" if done else "#4a5070",
                          font=(F_JP, 9, "bold"))
            x += 60
        self.bar_t = 0

    def draw(self):
        real = self.cv.winfo_width()
        if real < 50 or real == self.width:
            return
        self.width = real
        width = real / S
        cv = self.cv
        cv.delete("all")
        owned = self.api.data["owned"]
        cols = max(3, min(7, (width - 30) // 124))
        tw, th, gap = 112, 124, 12
        x0 = (width - (cols * tw + (cols - 1) * gap)) / 2
        y = 16
        self.shimmer = []
        for r in reversed(ORDER):                         # いいものから並べる
            rate, items = POOL[r]
            col = RCOL[r]
            got = sum(1 for it in items if it in owned)
            done = r in self.api.data["complete"]
            cv.create_text(x0, y + 14, text=r, anchor="w", fill=col, font=(F_BIG, 22),
                           tags=("urtext",) if r == "UR" else ())
            cv.create_text(x0 + 80, y + 10, text=RNAME[r], anchor="w", fill="#c9d1ea", font=(F_JP, 10, "bold"))
            cv.create_text(x0 + 80, y + 27, text=f"出る確率 {rate}%", anchor="w", fill="#5b6588", font=(F_JP, 9))
            bx = x0 + 230
            bw = 180
            cv.create_rectangle(bx, y + 10, bx + bw, y + 22, fill="#141828", outline="#2a3150")
            cv.create_rectangle(bx, y + 10, bx + bw * got / len(items), y + 22, fill=col, outline="")
            cv.create_text(bx + bw + 10, y + 16, text=f"{got}/{len(items)}", anchor="w", fill="white",
                           font=(F_BIG, 10))
            if done:
                cv.create_text(bx + bw + 70, y + 16, text="👑 COMPLETE", anchor="w", fill=RCOL["SSR"],
                               font=(F_BIG, 10))
            y += 44
            for i, it in enumerate(items):
                cx = x0 + (i % cols) * (tw + gap)
                cy = y + (i // cols) * (th + gap)
                tag = f"t_{r}_{i}"
                n = owned.get(it)
                if n:
                    emo, name = split_item(it)
                    rid = cv.create_rectangle(cx, cy, cx + tw, cy + th, fill=mix(col, "#0a0c16", 0.8), outline=col,
                                              width=2, tags=(tag,))
                    cv.create_rectangle(cx, cy, cx + tw, cy + 6, fill=col, outline="", tags=(tag,))
                    cv.create_text(cx + tw / 2, cy + 46, text=emo, fill="white", font=(F_EMOJI, 30), tags=(tag,))
                    cv.create_text(cx + tw / 2, cy + 94, text=name, fill="white", width=tw - 10, justify="center",
                                   font=(F_JP, 9, "bold"), tags=(tag,))
                    cv.create_text(cx + tw - 6, cy + 16, text=f"×{n}", anchor="e", fill=col, font=(F_BIG, 9),
                                   tags=(tag,))
                    if rank(r) >= 3:
                        self.shimmer.append((rid, r, i))
                    cv.tag_bind(tag, "<Button-1>", lambda e, rr=r, ii=it, nn=n: self.open_item(rr, ii, nn))
                    cv.tag_bind(tag, "<Enter>", lambda e, q=rid: self.hover_on(q))
                    cv.tag_bind(tag, "<Leave>", lambda e, q=rid, c=col: self.hover_off(q, c))
                else:
                    cv.create_rectangle(cx, cy, cx + tw, cy + th, fill="#0e1019", outline="#232838", width=2)
                    cv.create_text(cx + tw / 2, cy + 50, text="?", fill="#2a3048", font=(F_BIG, 34))
                    cv.create_text(cx + tw / 2, cy + 96, text="？？？", fill="#3a4060", font=(F_JP, 9, "bold"))
            rows = (len(items) + cols - 1) // cols
            y += rows * (th + gap) + 22
        cv.create_text(width / 2, y + 4, text="持っているアイテムをクリックすると大きく表示します",
                       fill="#4a5070", font=(F_JP, 9))
        cv.configure(scrollregion=(0, 0, real, (y + 30) * S))

    def hover_on(self, rid):
        self.hover = rid
        self.cv.itemconfigure(rid, outline="white", width=3)
        self.cv.configure(cursor="hand2")

    def hover_off(self, rid, col):
        self.hover = None
        self.cv.itemconfigure(rid, outline=col, width=2)
        self.cv.configure(cursor="")

    def step(self):
        if not self.alive():
            return
        try:
            self.t += 1
            # 全体の進み具合のバーを伸ばす
            if self.bar_t < 24:
                self.bar_t += 1
                w = 400 * self.ratio * ease_out(self.bar_t / 24)
                self.head.coords("bar", 24, 82, 24 + w, 98)
                self.head.itemconfigure("bar", fill=hsv(self.t / 40) if self.ratio >= 1 else RCOL["SSR"])
            elif self.ratio >= 1:
                self.head.itemconfigure("bar", fill=hsv(self.t / 40))
            # SSR・UR のアイテムはふちが光る
            for rid, r, i in self.shimmer:
                if r == "UR":
                    c = hsv(self.t / 30 + i * 0.3)
                else:
                    c = mix(RCOL["SSR"], "#ffffff", 0.5 + 0.5 * math.sin(self.t / 6 + i))
                if rid != self.hover:
                    self.cv.itemconfigure(rid, outline=c)
            self.cv.itemconfigure("urtext", fill=hsv(self.t / 40))
        except tk.TclError:
            self.dead = True
            return
        self.api.after(FRAME_MS, self.step)


# ---- MOD 本体 ----
_G = {}


def setup(api):
    api.data.setdefault("tickets", 0)
    api.data.setdefault("owned", {})       # アイテム → 個数
    api.data.setdefault("pulls", 0)
    api.data.setdefault("pity", 0)         # SSR 以上が出ていない回数
    api.data.setdefault("complete", [])    # コンプしたレア度
    api.data.setdefault("sound", True)
    global S
    try:
        S = max(1.0, api.root.winfo_fpixels("1i") / 96)
    except tk.TclError:
        S = 1.0
    s = {"sec": 0, "last": None}
    w = {"show": None, "book": None}
    sound = Sound(api.data["sound"])
    _G["sound"] = sound
    _G["w"] = w

    def total_items():
        return sum(len(v[1]) for v in POOL.values())

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(side="left")
        w["snd"] = ttk.Button(frame, width=3, command=toggle_sound)
        w["snd"].pack(side="right", padx=(4, 0))
        ttk.Button(frame, text="📖 図鑑", command=book).pack(side="right")
        ttk.Button(frame, text="10連", command=lambda: pull(10)).pack(side="right", padx=4)
        ttk.Button(frame, text="1回引く", command=lambda: pull(1)).pack(side="right")
        render()

    def render():
        if w.get("snd") and w["snd"].winfo_exists():
            w["snd"].configure(text="🔊" if api.data["sound"] else "🔇")
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        left = (TICKET_SEC - s["sec"]) // 60
        w["l"].configure(text=f"🎟 {api.data['tickets']} 枚 · 図鑑 {len(api.data['owned'])}/{total_items()}"
                              f" · 天井まで {PITY - api.data['pity']} · 次まで {left}分")

    def toggle_sound():
        api.data["sound"] = not api.data["sound"]
        sound.enabled = api.data["sound"]
        if not sound.enabled:
            sound.stop()
        api.save_data()
        render()

    def draw_results(n):
        """引く中身を決める（まだ保存しない）"""
        pity = api.data["pity"]
        out = []
        for _ in range(n):
            rarity, item = roll("SSR" if pity >= PITY - 1 else None)
            pity = 0 if rank(rarity) >= rank("SSR") else pity + 1
            out.append((rarity, item))
        if n == 10 and all(rank(r) < rank("SR") for r, _ in out):
            out[-1] = roll("SR")                      # 10連は SR 以上を1つ確定
        return out

    def commit(out):
        results = []
        for rarity, item in out:
            api.data["pity"] = 0 if rank(rarity) >= rank("SSR") else api.data["pity"] + 1
            new = item not in api.data["owned"]
            api.data["owned"][item] = api.data["owned"].get(item, 0) + 1
            api.data["pulls"] += 1
            results.append((rarity, item, new))
        return results

    def check_complete():
        for rarity, (rate, items) in POOL.items():
            if rarity not in api.data["complete"] and all(it in api.data["owned"] for it in items):
                api.data["complete"].append(rarity)
                bonus = rank(rarity) + 1
                api.data["tickets"] += bonus
                api.notify(f"📖 {rarity} をコンプリート！ ごほうびチケット +{bonus} 枚")

    def close_show():
        if w["show"]:
            w["show"].on_close = None
            w["show"].close()
            w["show"] = None

    def shown_closed(show):
        if w["show"] is show:
            w["show"] = None

    def pull(n):
        if api.data["tickets"] < n:
            messagebox.showinfo("作業ガチャ", f"チケットが足りません（{api.data['tickets']} / {n} 枚）。"
                                              "作業30分で1枚もらえます！", parent=api.root)
            return
        api.data["tickets"] -= n
        results = commit(draw_results(n))
        check_complete()
        api.save_data()
        render()
        if w["book"]:
            w["book"].refresh()
        close_show()
        w["show"] = GachaShow(api, results, sound, "pull", on_again=pull, on_book=book, on_close=shown_closed)

    def open_item(rarity, item, count):
        close_show()
        w["show"] = GachaShow(api, [(rarity, item, False)], sound, "view", on_close=shown_closed, count=count)

    def book_closed(b):
        if w["book"] is b:
            w["book"] = None

    def book():
        if w["book"] and w["book"].alive():
            w["book"].refresh()
            w["book"].top.lift()
            w["book"].top.focus_force()
            return
        w["book"] = Book(api, open_item, book_closed)

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= TICKET_SEC:
            s["sec"] -= TICKET_SEC
            api.data["tickets"] += 1
            api.save_data()
            api.notify(f"🎟 ガチャチケットをゲット！（{api.data['tickets']} 枚）")
            render()
        if datetime.now().second == 0:
            render()

    @api.on("goal_reached")
    def goal(goal_min, streak):
        api.data["tickets"] += 2
        api.save_data()
        api.notify("🎟 目標達成ボーナス！ チケット +2 枚")
        render()

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    def warm_fonts():
        # 絵文字のフォントは最初の1回の読み込みに時間がかかるので、演出の前に読んでおく
        try:
            for size in (30, 34, 78):
                tkfont.Font(root=api.root, family=F_EMOJI, size=size).measure("🌌👑🍙")
        except tk.TclError:
            pass

    api.after(5000, warm_fonts)
    api.add_panel(build, title="作業ガチャ")
    api.add_action("ガチャを引く", lambda: pull(1))
    api.add_action("10連ガチャ", lambda: pull(10))
    api.add_action("図鑑を見る", book)
    api.add_action("効果音 オン/オフ", toggle_sound)


def teardown(api):
    w = _G.get("w") or {}
    for key in ("show", "book"):
        win = w.get(key)
        if win:
            win.on_close = None
            win.close()
    if _G.get("sound"):
        _G["sound"].close()
