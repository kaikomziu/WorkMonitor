"""Plants! MOD

作業している時間だけ、メイン画面の鉢植えが育っていきます。
最後まで育ったら収穫して「記録」に残し、次の植物を選んでまた育てます。
"""

import math
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

MOD_INFO = {
    "name": "Plants!",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業時間に応じて鉢植えの植物が育ちます。育ちきったら収穫して記録に残し、次の植物を選んで育てましょう。",
    "api": 1,
}

# 植物の種類: ID → (表示名, 絵文字, 育ちきるまでの作業時間（分）)
PLANTS = {
    "tulip":         ("チューリップ", "🌷", 30),
    "morning_glory": ("アサガオ",     "🌺", 40),
    "strawberry":    ("イチゴ",       "🍓", 45),
    "lavender":      ("ラベンダー",   "🪻", 50),
    "sunflower":     ("ひまわり",     "🌻", 60),
    "carrot":        ("にんじん",     "🥕", 75),
    "cosmos":        ("コスモス",     "🏵️", 80),
    "cactus":        ("サボテン",     "🌵", 90),
    "lily":          ("ユリ",         "💐", 100),
    "tomato":        ("トマト",       "🍅", 120),
    "eggplant":      ("ナス",         "🍆", 150),
    "rose":          ("バラ",         "🌹", 180),
    "blueberry":     ("ブルーベリー", "🫐", 240),
    "sakura":        ("桜の盆栽",     "🌸", 300),
}

STAGES = ["たね", "芽", "若葉", "すくすく", "つぼみ", "収穫できます！"]

W, H = 150, 165          # 鉢のキャンバスの大きさ
CX, GROUND = 75, 122     # 茎の根元（土の上）

# オーバーレイ（デスクトップに浮かべる鉢）
OV_KEY = "#010203"                              # この色は透明になる
OV_SIZES = {"小": 0.7, "中": 1.0, "大": 1.4}
_overlays = {}                                  # MOD の ID → オーバーレイを閉じる関数


def stage_of(p):
    return 5 if p >= 1 else min(4, int(p * 5))


def fmt_min(sec):
    m = int(sec) // 60
    return f"{m // 60}時間{m % 60}分" if m >= 60 else f"{m}分"


# ---------------------------------------------------------------- 描画

def leaf(c, x, y, dx, dy, size, color):
    """(x, y) から (dx, dy) の向きに伸びる葉っぱ"""
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    tx, ty = x + ux * size, y + uy * size
    mx, my = x + ux * size * 0.5, y + uy * size * 0.5
    wd = size * 0.3
    c.create_polygon(x, y, mx + px * wd, my + py * wd, tx, ty, mx - px * wd, my - py * wd,
                     fill=color, outline="", smooth=True)


def draw_pot(c):
    c.create_polygon(42, 120, 108, 120, 100, 160, 50, 160, fill="#c56a3a", outline="")
    c.create_rectangle(38, 114, 112, 124, fill="#d77b48", outline="")
    c.create_oval(44, 116, 106, 126, fill="#5b3a24", outline="")


def draw_stem(c, h, color="#4f9a3a", width=3):
    c.create_line(CX, GROUND, CX, GROUND - h, fill=color, width=width, capstyle="round")


def draw_leaves(c, h, count, size, color="#5cb048"):
    for i in range(count):
        y = GROUND - h * (0.25 + 0.6 * i / max(1, count))
        side = -1 if i % 2 == 0 else 1
        leaf(c, CX, y, side * 1.0, -0.45, size, color)


def draw_sprout(c, p):
    # たね〜芽の段階はどの植物も共通
    if p < 0.05:
        c.create_oval(CX - 4, GROUND - 3, CX + 4, GROUND + 2, fill="#8a5a2b", outline="")
        return
    h = 4 + p * 60
    draw_stem(c, h, width=2)
    s = 6 + p * 40
    leaf(c, CX, GROUND - h, -1, -0.5, s, "#72c25a")
    leaf(c, CX, GROUND - h, 1, -0.5, s, "#72c25a")


def draw_sunflower(c, p, st):
    h = 20 + p * 75
    draw_stem(c, h, width=4)
    draw_leaves(c, h, 2 + st, 16 + p * 8)
    top = GROUND - h
    if st == 4:
        c.create_oval(CX - 7, top - 10, CX + 7, top + 2, fill="#7fb24a", outline="")
    elif st == 5:
        for i in range(14):
            a = math.pi * 2 * i / 14
            x, y = CX + math.cos(a) * 15, top + math.sin(a) * 15
            c.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#ffcc1a", outline="")
        c.create_oval(CX - 11, top - 11, CX + 11, top + 11, fill="#6b3f1d", outline="")


def draw_tulip(c, p, st):
    h = 15 + p * 45
    draw_stem(c, h)
    for side in (-1, 1):
        leaf(c, CX, GROUND - 2, side * 0.4, -1, 18 + p * 22, "#5cb048")
    top = GROUND - h
    if st == 4:
        c.create_oval(CX - 5, top - 14, CX + 5, top + 2, fill="#e9a0a8", outline="")
    elif st == 5:
        c.create_polygon(CX - 13, top - 18, CX - 6, top - 8, CX, top - 20, CX + 6, top - 8,
                         CX + 13, top - 18, CX + 11, top, CX - 11, top,
                         fill="#e8414f", outline="")
        c.create_oval(CX - 11, top - 8, CX + 11, top + 6, fill="#e8414f", outline="")


def draw_strawberry(c, p, st):
    h = 14 + p * 34
    for dx in (-24, 0, 24):
        x = CX + dx * p
        c.create_line(CX, GROUND, x, GROUND - h, fill="#4f9a3a", width=2)
        for a in (-1, 0, 1):
            leaf(c, x, GROUND - h, a * 0.8, -1, 11 + p * 8, "#4e9e3c")
    if st >= 4:
        for x, y in ((CX - 40, GROUND), (CX + 40, GROUND + 6), (CX + 12, GROUND - 14)):
            c.create_line(CX, GROUND - h * 0.6, x, y - 6, fill="#4f9a3a", width=1)
            if st == 4:
                for dx, dy in ((0, -3), (3, 0), (0, 3), (-3, 0)):
                    c.create_oval(x + dx - 3, y + dy - 3, x + dx + 3, y + dy + 3, fill="white", outline="")
                c.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#f2c12e", outline="")
            else:
                c.create_polygon(x - 8, y - 6, x + 8, y - 6, x, y + 10, fill="#e3263b", outline="", smooth=True)
                c.create_oval(x - 8, y - 9, x + 8, y + 2, fill="#e3263b", outline="")
                for sx, sy in ((-3, -3), (3, -3), (0, 1), (-2, 4), (2, 4)):
                    c.create_oval(x + sx - 1, y + sy - 1, x + sx + 1, y + sy + 1, fill="#ffe08a", outline="")
                leaf(c, x, y - 8, -1, -0.3, 5, "#3f8a30")
                leaf(c, x, y - 8, 1, -0.3, 5, "#3f8a30")


def draw_cactus(c, p, st):
    h = 18 + p * 60
    g, dark = "#4c9a4f", "#3a7d3e"
    c.create_oval(CX - 13, GROUND - h, CX + 13, GROUND - h + 26, fill=g, outline="")
    c.create_rectangle(CX - 13, GROUND - h + 13, CX + 13, GROUND + 2, fill=g, outline="")
    if p > 0.4:  # 左の腕
        ah = min(1, (p - 0.4) / 0.4) * 22
        y = GROUND - h * 0.45
        c.create_rectangle(CX - 26, y - 6, CX - 12, y + 4, fill=g, outline="")
        c.create_oval(CX - 32, y - 6 - ah, CX - 20, y - ah + 6, fill=g, outline="")
        c.create_rectangle(CX - 32, y - ah, CX - 20, y + 4, fill=g, outline="")
    if p > 0.6:  # 右の腕
        ah = min(1, (p - 0.6) / 0.35) * 18
        y = GROUND - h * 0.65
        c.create_rectangle(CX + 12, y - 6, CX + 26, y + 4, fill=g, outline="")
        c.create_oval(CX + 20, y - 6 - ah, CX + 32, y - ah + 6, fill=g, outline="")
        c.create_rectangle(CX + 20, y - ah, CX + 32, y + 4, fill=g, outline="")
    for i in range(int(h // 12)):
        y = GROUND - 6 - i * 12
        c.create_line(CX - 5, y, CX - 8, y - 3, fill=dark)
        c.create_line(CX + 5, y - 6, CX + 8, y - 9, fill=dark)
    top = GROUND - h
    if st == 4:
        c.create_oval(CX - 4, top - 6, CX + 4, top + 2, fill="#f08cc0", outline="")
    elif st == 5:
        for dx in (-7, 0, 7):
            c.create_oval(CX + dx - 6, top - 12, CX + dx + 6, top + 2, fill="#f05aa6", outline="")
        c.create_oval(CX - 3, top - 7, CX + 3, top - 1, fill="#ffe36b", outline="")


def draw_tomato(c, p, st):
    h = 20 + p * 60
    draw_stem(c, h, width=3)
    # わき芽の枝
    for i in range(1 + st):
        y = GROUND - h * (0.2 + 0.15 * i)
        side = -1 if i % 2 else 1
        x2 = CX + side * (14 + p * 14)
        c.create_line(CX, y, x2, y - 10, fill="#4f9a3a", width=2)
        leaf(c, x2, y - 10, side, -0.2, 12 + p * 6, "#4e9e3c")
        leaf(c, (CX + x2) / 2, y - 5, side * 0.3, -1, 9, "#5cb048")
    leaf(c, CX, GROUND - h, 0, -1, 12, "#5cb048")
    spots = ((CX - 18, GROUND - h * 0.45), (CX + 20, GROUND - h * 0.6), (CX - 8, GROUND - h * 0.8),
             (CX + 10, GROUND - h * 0.3))
    if st == 4:
        for x, y in spots:
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#f5d02c", outline="")
    elif st == 5:
        for x, y in spots:
            c.create_oval(x - 9, y - 8, x + 9, y + 9, fill="#e5302a", outline="")
            c.create_oval(x - 5, y - 5, x - 1, y - 1, fill="#ff8a7a", outline="")
            leaf(c, x, y - 8, -1, -0.4, 5, "#3f8a30")
            leaf(c, x, y - 8, 1, -0.4, 5, "#3f8a30")


def draw_rose(c, p, st):
    h = 20 + p * 65
    draw_stem(c, h, color="#3d7a32", width=3)
    for i in range(int(h // 14)):  # トゲ
        y = GROUND - 8 - i * 14
        side = -1 if i % 2 else 1
        c.create_polygon(CX, y, CX + side * 5, y - 3, CX, y - 4, fill="#2f5e27", outline="")
    draw_leaves(c, h, 1 + st, 13, color="#3f8a30")
    top = GROUND - h
    if st == 4:
        c.create_oval(CX - 5, top - 14, CX + 5, top + 1, fill="#b5162b", outline="")
        leaf(c, CX, top, -0.6, -1, 8, "#3f8a30")
        leaf(c, CX, top, 0.6, -1, 8, "#3f8a30")
    elif st == 5:
        for r, col in ((16, "#b5162b"), (12, "#d61f3a"), (8, "#e8314b"), (4, "#9e1024")):
            c.create_oval(CX - r, top - 6 - r, CX + r, top - 6 + r, fill=col, outline="")
        c.create_arc(CX - 10, top - 16, CX + 10, top + 2, start=200, extent=140, style="arc",
                     outline="#8a0d1f", width=2)


def draw_morning_glory(c, p, st):
    h = 25 + p * 62
    c.create_line(CX + 2, GROUND, CX + 2, GROUND - h - 8, fill="#b08a5a", width=3)   # 支柱
    pts = []
    for i in range(25):
        y = GROUND - h * i / 24
        pts += [CX + 2 + math.sin(i * 0.9) * 8, y]
    c.create_line(*pts, fill="#4f9a3a", width=2, smooth=True)
    for i in range(2 + st):
        y = GROUND - h * (0.15 + 0.75 * i / (2 + st))
        side = -1 if i % 2 else 1
        leaf(c, CX + 2 + side * 6, y, side, -0.3, 13, "#5cb048")
        leaf(c, CX + 2 + side * 6, y, side, 0.3, 9, "#5cb048")
    spots = ((CX - 18, GROUND - h * 0.75), (CX + 22, GROUND - h * 0.5), (CX + 2, GROUND - h - 6))
    if st == 4:
        for x, y in spots:
            c.create_polygon(x - 2, y + 6, x + 2, y + 6, x, y - 8, fill="#8f7fe0", outline="", smooth=True)
    elif st == 5:
        for (x, y), col in zip(spots, ("#3f63e0", "#9b4fd8", "#e04fa6")):
            c.create_oval(x - 11, y - 11, x + 11, y + 11, fill=col, outline="")
            c.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#e8ecff", outline="")
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#f5e27a", outline="")


def draw_lavender(c, p, st):
    h = 18 + p * 55
    for side in (-1, 1):
        for i in range(3):
            leaf(c, CX, GROUND - 2, side * (0.4 + i * 0.4), -1, 12 + p * 8, "#8fae86")
    for j in range(-3, 4):
        x2, y2 = CX + j * 6 * (0.5 + p), GROUND - h * (1 - abs(j) * 0.08)
        c.create_line(CX, GROUND, x2, y2, fill="#7a9a6a", width=2)
        if st >= 4:
            col, r = ("#b9a3d6", 2) if st == 4 else ("#8a5cc7", 3)
            for k in range(6):
                t = k / 5
                x, y = x2 + (x2 - CX) * 0.08 * t, y2 - 16 * t
                c.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")


def draw_cosmos(c, p, st):
    h = 25 + p * 75
    tops = ((CX, GROUND - h), (CX - 26, GROUND - h * 0.7), (CX + 24, GROUND - h * 0.8))
    for i, (x, y) in enumerate(tops):
        bx, by = (CX, GROUND) if i == 0 else (CX, GROUND - h * 0.35)
        c.create_line(bx, by, x, y, fill="#4f9a3a", width=2)
        for k in range(1, 5):   # 細い羽のような葉
            t = k / 5
            mx, my = bx + (x - bx) * t, by + (y - by) * t
            for sd in (-1, 1):
                c.create_line(mx, my, mx + sd * 7, my - 5, fill="#5cb048", width=1)
    if st == 4:
        for x, y in tops:
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#6aa84f", outline="")
    elif st == 5:
        for (x, y), col in zip(tops, ("#f27aa8", "#ffffff", "#d83a8a")):
            for i in range(8):
                a = math.pi * 2 * i / 8
                px, py = x + math.cos(a) * 9, y + math.sin(a) * 9
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill=col, outline="")
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#f2c12e", outline="")


def draw_carrot(c, p, st):
    if st >= 3:   # 土から顔を出すにんじんの肩
        r = 6 + (st - 3) * 5
        c.create_arc(CX - r, GROUND - r, CX + r, GROUND + r, start=0, extent=180,
                     fill="#f08a24", outline="")
        if st == 5:
            c.create_line(CX - 4, GROUND - 6, CX + 2, GROUND - 6, fill="#c96a14")
    n = 5
    for j in range(n):
        a = math.pi * (0.25 + 0.5 * j / (n - 1))
        ln = 20 + p * 50
        x2, y2 = CX - math.cos(a) * ln * 0.6, GROUND - math.sin(a) * ln
        c.create_line(CX, GROUND - 4, x2, y2, fill="#4f9a3a", width=2)
        for k in range(2, 7):   # ふさふさの葉
            t = k / 7
            mx, my = CX + (x2 - CX) * t, GROUND - 4 + (y2 - GROUND + 4) * t
            c.create_oval(mx - 4, my - 3, mx + 4, my + 3, fill="#5cb048", outline="")


def draw_lily(c, p, st):
    h = 20 + p * 62
    draw_stem(c, h, width=3)
    for i in range(3 + st):
        y = GROUND - h * (0.1 + 0.8 * i / (3 + st))
        side = -1 if i % 2 else 1
        leaf(c, CX, y, side * 0.6, -1, 16, "#4e9e3c")
    top = GROUND - h
    if st == 4:
        c.create_oval(CX - 5, top - 22, CX + 5, top + 2, fill="#dfe8c8", outline="")
    elif st == 5:
        for i in range(6):
            a = -math.pi / 2 + (i - 2.5) * 0.5
            x, y = CX + math.cos(a) * 18, top - 4 + math.sin(a) * 14
            leaf(c, CX, top, x - CX, y - top, 22, "#fdf6f0")
        for i in range(5):
            a = -math.pi / 2 + (i - 2) * 0.35
            x, y = CX + math.cos(a) * 12, top + math.sin(a) * 12
            c.create_line(CX, top, x, y, fill="#7a9a3a")
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#e07a1c", outline="")


def draw_eggplant(c, p, st):
    h = 20 + p * 55
    draw_stem(c, h, color="#5b4a6b", width=3)
    for i in range(1 + st):
        y = GROUND - h * (0.25 + 0.15 * i)
        side = -1 if i % 2 else 1
        x2 = CX + side * (12 + p * 12)
        c.create_line(CX, y, x2, y - 8, fill="#5b4a6b", width=2)
        leaf(c, x2, y - 8, side, -0.3, 16 + p * 6, "#4e8a3c")
    leaf(c, CX, GROUND - h, 0, -1, 14, "#4e8a3c")
    spots = ((CX - 16, GROUND - h * 0.5), (CX + 18, GROUND - h * 0.65), (CX + 4, GROUND - h * 0.3))
    if st == 4:
        for x, y in spots:
            for i in range(5):
                a = math.pi * 2 * i / 5
                px, py = x + math.cos(a) * 3, y + math.sin(a) * 3
                c.create_oval(px - 3, py - 3, px + 3, py + 3, fill="#a77fd6", outline="")
            c.create_oval(x - 1, y - 1, x + 1, y + 1, fill="#f5d02c", outline="")
    elif st == 5:
        for x, y in spots:
            c.create_oval(x - 7, y, x + 7, y + 24, fill="#4b2a6b", outline="")
            c.create_oval(x - 4, y + 4, x - 1, y + 12, fill="#7a55a0", outline="")
            c.create_polygon(x - 7, y + 4, x, y - 3, x + 7, y + 4, x, y + 2, fill="#3f7a30", outline="")


def draw_blueberry(c, p, st):
    h = 20 + p * 55
    ends = ((CX - 28 * p - 6, GROUND - h * 0.8), (CX, GROUND - h), (CX + 28 * p + 6, GROUND - h * 0.75))
    for x, y in ends:
        c.create_line(CX, GROUND, (CX + x) / 2, GROUND - h * 0.4, x, y, fill="#7a5a3a", width=3, smooth=True)
        for k in range(2, 6):
            t = k / 6
            mx, my = CX + (x - CX) * t, GROUND - (GROUND - y) * t
            c.create_oval(mx - 6, my - 4, mx + 2, my + 2, fill="#4e9e3c", outline="")
            c.create_oval(mx - 1, my - 6, mx + 6, my, fill="#5cb048", outline="")
    if st == 4:
        for x, y in ends:
            for dx in (-5, 0, 5):
                c.create_oval(x + dx - 2, y - 2, x + dx + 3, y + 4, fill="#f4f0e6", outline="")
    elif st == 5:
        for x, y in ends:
            for dx, dy in ((-6, 0), (0, -5), (5, 1), (-1, 5), (6, 7)):
                bx, by = x + dx, y + dy
                c.create_oval(bx - 4, by - 4, bx + 4, by + 4, fill="#3a4fa3", outline="")
                c.create_oval(bx - 2, by - 3, bx, by - 1, fill="#8c9ad6", outline="")


def draw_sakura(c, p, st):
    tw = 5 + p * 5   # 幹の太さ
    th = 30 + p * 30
    c.create_polygon(CX - tw, GROUND, CX + tw, GROUND, CX + 10 + tw * 0.5, GROUND - th * 0.5,
                     CX + 4, GROUND - th, CX - 2, GROUND - th, CX + 4, GROUND - th * 0.5,
                     fill="#6b4630", outline="", smooth=True)
    tip = (CX + 1, GROUND - th)
    branches = ((CX - 30 * p - 8, GROUND - th - 4), (CX + 30 * p + 8, GROUND - th + 6),
                (CX + 2, GROUND - th - 18 * p - 6))
    for x, y in branches:
        c.create_line(*tip, x, y, fill="#6b4630", width=3, capstyle="round")
    blobs = list(branches) + [tip]
    r = 8 + p * 10
    if st <= 3:
        for x, y in blobs:
            c.create_oval(x - r, y - r * 0.7, x + r, y + r * 0.7, fill="#5cb048", outline="")
    else:
        cols = ("#f7c6d4", "#f49ac1") if st == 5 else ("#7fb85a", "#6aa84f")
        for i, (x, y) in enumerate(blobs):
            c.create_oval(x - r, y - r * 0.75, x + r, y + r * 0.75, fill=cols[i % 2], outline="")
        if st == 4:   # つぼみ
            for x, y in blobs:
                for dx, dy in ((-5, -2), (4, 3), (1, -6)):
                    c.create_oval(x + dx - 2, y + dy - 2, x + dx + 2, y + dy + 2, fill="#f49ac1", outline="")
        else:         # 花びらが舞う
            for x, y in ((CX - 40, GROUND - 20), (CX + 38, GROUND - 30), (CX - 20, GROUND - 6)):
                c.create_oval(x - 3, y - 2, x + 3, y + 2, fill="#f7c6d4", outline="")


DRAW = {
    "sunflower": draw_sunflower, "tulip": draw_tulip, "strawberry": draw_strawberry,
    "cactus": draw_cactus, "tomato": draw_tomato, "rose": draw_rose,
    "morning_glory": draw_morning_glory, "lavender": draw_lavender, "cosmos": draw_cosmos,
    "carrot": draw_carrot, "lily": draw_lily, "eggplant": draw_eggplant,
    "blueberry": draw_blueberry, "sakura": draw_sakura,
}


def draw_plant(c, kind, p, bg, scale=1.0):
    c.delete("all")
    c.configure(bg=bg)
    draw_pot(c)
    if kind:
        st = stage_of(p)
        # サボテン以外は「芽」の段階までは共通の芽を描く
        if st < 2 and kind != "cactus":
            draw_sprout(c, p * 2.5)
        else:
            DRAW[kind](c, min(p, 1), st)
        if st == 5:
            for x, y in ((25, 30), (125, 45), (30, 85), (120, 95)):  # キラキラ
                c.create_text(x, y, text="✦", fill="#ffd34d", font=("Segoe UI", 10))
    if scale != 1.0:
        c.scale("all", 0, 0, scale, scale)


# ---------------------------------------------------------------- MOD 本体

def setup(api):
    api.data.setdefault("current", None)   # {"kind", "sec", "planted"} か None
    api.data.setdefault("records", [])     # 収穫した植物の一覧
    api.data.setdefault("overlay", {"on": False, "x": None, "y": None, "size": "中"})
    s = {"last": None, "unsaved": 0, "drawn": None}
    w = {}
    ov = {"win": None, "drawn": None, "drag": None}

    def cur():
        return api.data["current"]

    def progress():
        c = cur()
        return min(1.0, c["sec"] / (PLANTS[c["kind"]][2] * 60)) if c else 0.0

    # メイン画面の枠（作り直されても状態は api.data に持っているので大丈夫）
    def build(frame):
        w.clear()
        s["drawn"] = None
        w["canvas"] = tk.Canvas(frame, width=W, height=H, highlightthickness=0, bd=0)
        w["canvas"].pack(side="left", padx=(0, 12))
        right = ttk.Frame(frame)
        right.pack(side="left", fill="both", expand=True, anchor="n")

        c = cur()
        if c:
            name, emoji, _ = PLANTS[c["kind"]]
            ttk.Label(right, text=f"{emoji} {name}", font=("Segoe UI", 13, "bold")).pack(anchor="w")
            w["stage"] = ttk.Label(right, foreground=api.colors["sub"])
            w["stage"].pack(anchor="w", pady=(2, 6))
            w["bar"] = ttk.Progressbar(right, maximum=1000, length=200)
            w["bar"].pack(anchor="w", fill="x")
            w["time"] = ttk.Label(right, foreground=api.colors["sub"])
            w["time"].pack(anchor="w", pady=(4, 8))
            btns = ttk.Frame(right)
            btns.pack(anchor="w")
            w["harvest"] = ttk.Button(btns, text="🧺 収穫する", command=harvest)
            w["harvest"].pack(side="left", padx=(0, 6))
        else:
            ttk.Label(right, text="次に育てる植物を選んでください",
                      font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
            labels = [f"{e} {n}（作業 {fmt_min(m * 60)}）" for n, e, m in PLANTS.values()]
            w["choice"] = ttk.Combobox(right, values=labels, state="readonly", width=24, height=len(labels))
            w["choice"].current(0)
            w["choice"].pack(anchor="w", pady=(0, 8))
            w["choice"].bind("<<ComboboxSelected>>", lambda e: preview())
            btns = ttk.Frame(right)
            btns.pack(anchor="w")
            ttk.Button(btns, text="🌱 植える", command=plant).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text=f"📖 記録（{len(api.data['records'])}）", command=show_records).pack(side="left")
        w["ov_btn"] = ttk.Button(btns, command=toggle_overlay)
        w["ov_btn"].pack(side="left", padx=(6, 0))
        render()
        if not c:
            preview()

    def preview():
        # 選んでいる植物の完成イメージを鉢に描く
        cv = w.get("canvas")
        if cv and cv.winfo_exists() and "choice" in w:
            draw_plant(cv, list(PLANTS)[w["choice"].current()], 1.0, api.colors["bg"])
            cv.create_text(W / 2, 8, text="完成イメージ", fill=api.colors["sub"], font=("Segoe UI", 8))

    def render():
        render_overlay()
        cv = w.get("canvas")
        if not cv or not cv.winfo_exists():
            return
        c, p = cur(), progress()
        if "ov_btn" in w:
            w["ov_btn"].configure(text="🪟 デスクトップから戻す" if overlay_alive() else "🪟 デスクトップに出す")
        key = (c["kind"] if c else None, int(p * 100), api.dark)
        if c and key != s["drawn"]:   # 1% 進むごとに描き直す
            s["drawn"] = key
            draw_plant(cv, c["kind"] if c else None, p, api.colors["bg"])
        if c and "bar" in w:
            need = PLANTS[c["kind"]][2] * 60
            w["stage"].configure(text=f"{STAGES[stage_of(p)]}　{int(p * 100)}%")
            w["bar"].configure(value=int(p * 1000))
            w["time"].configure(text=f"{fmt_min(min(c['sec'], need))} / {fmt_min(need)}"
                                + ("" if p >= 1 else f"（あと {fmt_min(need - c['sec'] + 59)}）"))
            w["harvest"].configure(state="normal" if p >= 1 else "disabled")

    def rebuild():
        api.after(0, api.refresh_panels)
        api.after(0, render_overlay)

    # ------------------------------------------------ オーバーレイ
    def overlay_alive():
        win = ov["win"]
        return bool(win) and win.winfo_exists()

    def open_overlay():
        if overlay_alive():
            return
        conf = api.data["overlay"]
        f = OV_SIZES.get(conf.get("size"), 1.0)
        win = tk.Toplevel(api.root)
        win.overrideredirect(True)          # 枠なし
        win.attributes("-topmost", True)    # いつも手前
        try:
            win.attributes("-transparentcolor", OV_KEY)
        except tk.TclError:
            pass
        win.configure(bg=OV_KEY)
        cv = tk.Canvas(win, width=int(W * f), height=int((H + 26) * f), bg=OV_KEY,
                       highlightthickness=0, bd=0, cursor="fleur")
        cv.pack()
        x, y = conf.get("x"), conf.get("y")
        if x is None or y is None:
            x, y = win.winfo_screenwidth() - int(W * f) - 40, 120
        win.geometry(f"+{x}+{y}")

        def press(e):
            ov["drag"] = (e.x_root - win.winfo_x(), e.y_root - win.winfo_y())

        def move(e):
            if ov["drag"]:
                win.geometry(f"+{e.x_root - ov['drag'][0]}+{e.y_root - ov['drag'][1]}")

        def release(e):
            ov["drag"] = None
            conf.update(x=win.winfo_x(), y=win.winfo_y())
            api.save_data()

        def menu(e):
            m = tk.Menu(win, tearoff=0)
            m.add_command(label="🧺 収穫する", command=harvest,
                          state="normal" if cur() and progress() >= 1 else "disabled")
            m.add_command(label="📖 記録を見る", command=show_records)
            sizes = tk.Menu(m, tearoff=0)
            ov["size_var"] = var = tk.StringVar(m, conf.get("size", "中"))
            for name in OV_SIZES:
                sizes.add_radiobutton(label=name, value=name, variable=var,
                                      command=lambda n=name: resize_overlay(n))
            m.add_cascade(label="大きさ", menu=sizes)
            m.add_separator()
            m.add_command(label="デスクトップから戻す", command=toggle_overlay)
            m.tk_popup(e.x_root, e.y_root)

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", release)
        cv.bind("<Double-Button-1>", lambda e: harvest())   # 育ちきっていればダブルクリックで収穫
        cv.bind("<Button-3>", menu)
        ov.update(win=win, cv=cv, scale=f, drawn=None)
        render_overlay()

    def close_overlay():
        if overlay_alive():
            ov["win"].destroy()
        ov["win"] = None

    def toggle_overlay():
        conf = api.data["overlay"]
        if overlay_alive():
            close_overlay()
            conf["on"] = False
        else:
            open_overlay()
            conf["on"] = True
        api.save_data()
        render()

    def resize_overlay(name):
        api.data["overlay"]["size"] = name
        api.save_data()
        close_overlay()
        open_overlay()

    def render_overlay():
        if not overlay_alive():
            return
        cv, f = ov["cv"], ov["scale"]
        c, p = cur(), progress()
        key = (c["kind"] if c else None, int(p * 100))
        if key == ov["drawn"]:
            return
        ov["drawn"] = key
        draw_plant(cv, c["kind"] if c else None, p, OV_KEY, f)
        if c:
            name, emoji, _ = PLANTS[c["kind"]]
            text = f"{name} 収穫できます！" if p >= 1 else f"{name} {int(p * 100)}%"
        else:
            text = "次の植物を選んでね"
        x, y = W * f / 2, (H + 12) * f
        font = ("Segoe UI", max(8, int(10 * f)), "bold")
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):   # 縁どりで読みやすく
            cv.create_text(x + dx, y + dy, text=text, fill="#1a1a1a", font=font)
        cv.create_text(x, y, text=text, fill="#ffffff", font=font)

    _overlays[api.id] = close_overlay
    if api.data["overlay"].get("on"):
        api.after(0, open_overlay)

    def plant():
        kind = list(PLANTS)[w["choice"].current()]
        api.data["current"] = {"kind": kind, "sec": 0, "planted": datetime.now().isoformat(timespec="seconds")}
        api.save_data()
        api.log(f"{PLANTS[kind][0]} を植えました")
        rebuild()

    def harvest():
        c = cur()
        if not c or progress() < 1:
            return
        name, emoji, minutes = PLANTS[c["kind"]]
        api.data["records"].append({
            "kind": c["kind"], "name": name, "minutes": minutes,
            "planted": c.get("planted"), "harvested": datetime.now().isoformat(timespec="seconds"),
        })
        api.data["current"] = None
        api.save_data()
        api.notify(f"{emoji} {name} を収穫しました！（{len(api.data['records'])} 個目）")
        rebuild()
        show_records()

    def give_up():
        if cur() and messagebox.askyesno("Plants!", "いま育てている植物を抜いて、植え直しますか？\n（育てた時間はなくなります）",
                                             parent=api.root):
            api.data["current"] = None
            api.save_data()
            rebuild()

    def show_records():
        old = w.get("records_win")
        if old and old.winfo_exists():
            old.destroy()
        win = tk.Toplevel(api.root)
        w["records_win"] = win
        win.title("Plants! 記録")
        win.configure(bg=api.colors["bg"])
        k = win.winfo_fpixels("1i") / 96   # 高 DPI の画面でも窮屈にならないように
        style = ttk.Style(win)
        style.configure("Plants.Treeview", rowheight=int(26 * k))
        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)
        recs = api.data["records"]
        total = sum(r["minutes"] for r in recs)
        ttk.Label(body, text=f"収穫した植物　{len(recs)} 個（作業 {fmt_min(total * 60)}）",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        counts = []
        for kind, (name, emoji, _) in PLANTS.items():
            n = sum(1 for r in recs if r["kind"] == kind)
            if n:
                counts.append(f"{emoji}×{n}")
        ttk.Label(body, text="　".join(counts) or "まだありません。作業して育てましょう！",
                  foreground=api.colors["sub"], font=("Segoe UI", 11)).pack(anchor="w", pady=(4, 8))
        tree = ttk.Treeview(body, columns=("date", "plant", "time"), show="headings", height=10,
                            style="Plants.Treeview")
        for col, text, wd in (("date", "収穫した日", 150), ("plant", "植物", 150), ("time", "作業時間", 100)):
            tree.heading(col, text=text)
            tree.column(col, width=int(wd * k), anchor="w")
        for r in reversed(recs):
            emoji = PLANTS.get(r["kind"], ("", "🌿", 0))[1]
            date = r["harvested"].replace("T", " ")[:16]
            tree.insert("", "end", values=(date, f"{emoji} {r['name']}", fmt_min(r["minutes"] * 60)))
        sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

    @api.on("tick")
    def tick(status):
        # 前回からの作業時間の増え方だけ育てる（休憩中・数えないアプリでは育たない）
        last, s["last"] = s["last"], status["today_sec"]
        c = cur()
        if c and last is not None and status["today_sec"] > last:
            need = PLANTS[c["kind"]][2] * 60
            before = stage_of(progress())
            c["sec"] = min(need, c["sec"] + status["today_sec"] - last)
            s["unsaved"] += 1
            after = stage_of(progress())
            if after != before:
                if after == 5:
                    api.notify(f"{PLANTS[c['kind']][1]} {PLANTS[c['kind']][0]} が育ちきりました！収穫しましょう。")
                api.save_data()
                s["unsaved"] = 0
            elif s["unsaved"] >= 30:   # 30秒ごとに保存
                api.save_data()
                s["unsaved"] = 0
        render()

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    api.add_panel(build, title="Plants!（作業すると育ちます）")
    api.add_action("記録を見る", show_records)
    api.add_action("デスクトップに出す／戻す", toggle_overlay)
    api.add_action("いまの植物を抜いて植え直す", give_up)


def teardown(api):
    close = _overlays.pop(api.id, None)
    if close:
        close()
    api.save_data()
