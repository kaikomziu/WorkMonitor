"""いちばん小さい MOD の例

このファイルを WorkMonitor の画面にドラッグ＆ドロップすると追加されます。
"""

MOD_INFO = {
    "name": "Hello MOD",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業中・休憩中が切り替わるたびにログを書き、1日の目標を達成したらお祝いします。",
}


def setup(api):
    api.log("こんにちは！ WorkMonitor", api.version)

    @api.on("state_change")
    def changed(old, new, status):
        api.log(f"{old} → {new}（{status['app_name']}）")

    @api.on("goal_reached")
    def goal(goal_min, streak):
        api.notify(f"🎉 おめでとう！ {streak} 日連続で目標達成です")

    # 設定 → Mods でこの MOD を選ぶと出るボタン
    api.add_action("あいさつする", lambda: api.notify("こんにちは！"))


def teardown(api):
    api.log("さようなら")
