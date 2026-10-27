"""アイコン画像をコードで描く（タスクトレイ・ウィンドウ・exe 共通）"""

from PIL import Image, ImageDraw

BLUE = "#4f6bed"   # アプリのアイコン
GREEN = "#22a06b"  # 作業中
GRAY = "#8a919c"   # 休憩中


def make_image(size=64, color=BLUE):
    # 4倍で描いてから縮小してなめらかにする
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 5, fill=color)
    # 時計の文字盤
    m = s // 6
    w = max(4, s // 14)
    d.ellipse([m, m, s - m, s - m], outline="white", width=w)
    c = s // 2
    d.line([c, c, c, m + s // 7], fill="white", width=w)          # 長針
    d.line([c, c, c + s // 5, c + s // 9], fill="white", width=w)  # 短針
    d.ellipse([c - w, c - w, c + w, c + w], fill="white")
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path):
    make_image(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
