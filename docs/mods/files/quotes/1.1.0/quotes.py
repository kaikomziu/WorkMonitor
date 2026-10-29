"""名言

作業を始めたときに、ランダムな名言を通知します（30分に1回まで）。

1.1.0: 自分の好きなことばを追加できるように・お気に入り登録・名言を増量・同じものが続かないように
"""

import random
import time
from tkinter import messagebox, simpledialog

MOD_INFO = {
    "name": "名言",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "休憩から作業に戻ったとき、やる気の出る名言をランダムに通知します（30分に1回まで）。"
                   "自分のことばの追加・お気に入り登録もできます。",
    "api": 1,
}

QUOTES = [
    "千里の道も一歩から。 — 老子",
    "継続は力なり。",
    "今日できることを明日に延ばすな。 — ベンジャミン・フランクリン",
    "完璧を目指すよりまず終わらせろ。 — マーク・ザッカーバーグ",
    "始めるのに遅すぎることはない。",
    "小さなことを積み重ねることが、とんでもないところへ行くただひとつの道。 — イチロー",
    "成功は準備と機会が出会ったときに生まれる。 — セネカ",
    "やってみせ、言って聞かせて、させてみて、ほめてやらねば人は動かじ。 — 山本五十六",
    "為せば成る、為さねば成らぬ何事も。 — 上杉鷹山",
    "失敗したことがない人は、新しいことに挑戦したことがない人だ。 — アインシュタイン",
    "未来を予測する最善の方法は、それを発明することだ。 — アラン・ケイ",
    "シンプルさは究極の洗練である。 — レオナルド・ダ・ヴィンチ",
    "時は金なり。",
    "急がば回れ。",
    "塵も積もれば山となる。",
    "明日死ぬかのように生きよ。永遠に生きるかのように学べ。 — ガンジー",
    "やる気は行動のあとについてくる。",
    "まずは5分だけやってみよう。",
    "昨日の自分を超えればいい。",
    "早く行きたいなら一人で行け。遠くへ行きたいならみんなで行け。 — アフリカのことわざ",
    "石の上にも三年。",
    "好きこそ物の上手なれ。",
    "案ずるより産むが易し。",
    "知るを知るとなし、知らざるを知らずとなせ。これ知るなり。 — 孔子",
    "我々は繰り返し行うことの集大成である。 — アリストテレス",
    "行動はすべての成功への基本的な鍵である。 — パブロ・ピカソ",
    "簡単なことを確実にやれ。",
    "終わらせることは、始めることと同じくらい大事。",
    "疲れたら休め。休んだらまた進め。",
    "100点より、まず60点を出そう。",
]

COOLDOWN = 30 * 60


def setup(api):
    api.data.setdefault("custom", [])
    api.data.setdefault("favorites", [])
    s = {"last": 0, "bag": [], "current": ""}

    def pool():
        # お気に入りは2倍出やすくする
        return QUOTES + api.data["custom"] + api.data["favorites"]

    def show():
        if not s["bag"]:
            s["bag"] = random.sample(pool(), len(pool()))
        s["last"] = time.time()
        s["current"] = s["bag"].pop()
        api.notify(s["current"], title="💡 今日のことば")

    @api.on("state_change")
    def changed(old, new, status):
        if new == "working" and old != "working" and time.time() - s["last"] > COOLDOWN:
            show()

    def add():
        v = simpledialog.askstring("名言", "追加することば", parent=api.root)
        if v and v.strip():
            api.data["custom"].append(v.strip())
            api.save_data()
            s["bag"] = []

    def favorite():
        if not s["current"]:
            messagebox.showinfo("名言", "まだ名言が出ていません", parent=api.root)
            return
        if s["current"] not in api.data["favorites"]:
            api.data["favorites"].append(s["current"])
            api.save_data()
        api.log("お気に入りに追加:", s["current"])

    def show_list():
        lines = ["★ " + q for q in api.data["favorites"]] + ["＋ " + q for q in api.data["custom"]]
        messagebox.showinfo("名言", "\n".join(lines) or "お気に入りや追加したことばはまだありません", parent=api.root)

    def clear():
        if messagebox.askyesno("名言", "追加したことばとお気に入りをすべて消しますか？", parent=api.root):
            api.data.update({"custom": [], "favorites": []})
            api.save_data()
            s["bag"] = []

    api.add_action("名言を出す", show)
    api.add_action("自分のことばを追加", add)
    api.add_action("さっきの名言をお気に入りに", favorite)
    api.add_action("お気に入り・追加したことばを見る", show_list)
    api.add_action("追加したことば・お気に入りを全部消す", clear)
