==============================================================
  WorkMonitor の MOD の作り方（Earo MOD ローダー / API 1）
==============================================================

WorkMonitor には MOD ローダー「Earo」が入っています。
MOD はふつうの Python のプログラムです。setup(api) という関数を書くと、
WorkMonitor の起動時（または MOD をオンにしたとき）に呼ばれます。

  ⚠ MOD はこのアプリと同じ権限で動きます（ファイルの読み書き・通信もできます）。
    人からもらった MOD は、中身を確認するか、信頼できる人のものだけ入れてください。


--------------------------------------------------------------
 1. いちばん小さい MOD
--------------------------------------------------------------

  メモ帳などで、次の内容を「my_first_mod.py」という名前で保存します
  （文字コードは UTF-8）。

    MOD_INFO = {
        "name": "はじめての MOD",
        "version": "1.0.0",
        "author": "あなたの名前",
        "description": "作業中になったら通知します。",
    }

    def setup(api):
        @api.on("state_change")
        def changed(old, new, status):
            if new == "working":
                api.notify(f"{status['app_name']} で作業を始めました")

  このファイルを WorkMonitor のメイン画面（または 設定 → Mods）に
  ドラッグ＆ドロップすると、確認のあとで追加され、すぐに動き始めます。


--------------------------------------------------------------
 2. MOD の置き場所と形
--------------------------------------------------------------

  置き場所:  %APPDATA%\WorkMonitor\mods
             （設定 → Mods → 「MOD フォルダを開く」で開けます）

  MOD の形は3つあります。
    ・my_mod.py                 … ファイル1つの MOD
    ・my_mod\__init__.py        … フォルダの MOD（ファイルを分けたいとき）
                                   フォルダの中の別ファイルは
                                   from . import helper のように読み込めます
    ・my_mod.zip                … 上のどちらかを zip にしたもの（配布用）
                                   中身は「__init__.py が入ったフォルダ1つ」
                                   か「.py ファイル1つ」にしてください

  ファイル名（フォルダ名）がその MOD の ID になります。
    ・使える文字: 英数字・日本語・_・-（_ や . で始まる名前は読み込みません）
    ・同じ ID の MOD を入れると上書きされます

  mods フォルダに直接ファイルを置いた場合は、設定 → Mods の
  「すべて再読み込み」で一覧に出ます（最初はオフなので、オンにしてください）。

  mods\examples に作例があります（このフォルダの中は読み込まれません）。
    ・hello.py     … イベント・通知・ボタンの基本
    ・pomodoro.py  … メイン画面に枠を足す、オーバーレイの文字を変える、データを保存する


--------------------------------------------------------------
 3. MOD_INFO（なくても動きますが、書くのがおすすめ）
--------------------------------------------------------------

    MOD_INFO = {
        "name": "表示名",
        "version": "1.0.0",
        "author": "作者",
        "description": "説明（設定 → Mods に表示されます）",
        "api": 1,          # 必要な Earo の API の版。今は 1
    }

  MOD_INFO は、プログラムを実行せずに読み取って一覧に表示します。
  そのため、値は文字や数字をそのまま書いてください（計算や変数は使えません）。


--------------------------------------------------------------
 4. setup と teardown
--------------------------------------------------------------

  def setup(api):      … 必須。MOD を読み込んだときに1回呼ばれる
  def teardown(api):   … なくてもよい。MOD を止めるとき・アプリを終了するときに呼ばれる

  api.on() や api.after() で登録したものは、止めるときに自動で外れます。
  自分で作ったスレッドや開いたファイルは teardown で片付けてください。


--------------------------------------------------------------
 5. イベント   api.on("イベント名", 関数)   ／   @api.on("イベント名")
--------------------------------------------------------------

  "tick"           (status)                  約1秒ごと
  "state_change"   (old, new, status)        作業中・休憩中などが変わったとき
  "app_change"     (old_app, new_app, status) 前面のアプリが変わったとき（exe 名）
  "goal_reached"   (goal_min, streak)        1日の目標を達成したとき（1日1回）
                                              goal_min=目標（分）、streak=連続日数
  "day_change"     (day)                     日付が変わったとき（"2026-10-28" の形）
  "quit"           ()                        アプリを終了するとき

  状態（old / new / status["state"]）は次の3つです。
    "working"   … 作業中（数えるアプリを操作している）
    "idle"      … 休憩中（しばらく操作していない）
    "excluded"  … 数えないアプリを使っている

  status は次のような dict です（api.status() でいつでも取れます）。
    {
      "state": "working",
      "app": "code.exe",                 # 前面のアプリの exe 名
      "app_name": "VS Code",             # 表示名
      "category": "開発",
      "counted": True,                   # 作業に数えるアプリか
      "today_sec": 5025,                 # 今日の作業時間（秒）
      "today_by_app": {"VS Code": 3600, "Chrome": 1425},   # 表示名ごとの秒数
      "goal_min": 180,                   # 1日の目標（分。0 なら目標なし）
      "goal_done": False,
    }


--------------------------------------------------------------
 6. フィルター（表示する文字を書き換える）   @api.filter("名前")
--------------------------------------------------------------

  関数は文字を受け取り、書き換えた文字を返します。
  None や文字以外を返すと、元の文字のままになります。
  複数の MOD が登録したときは、読み込んだ順につながります。

  "overlay_text"  (text)        オーバーレイの2行目（例: "VS Code · 今日 1時間23分"）
  "discord_text"  (text, info)  Discord に出す文（例: "作業中"）
                                info は {"name", "category", "count", "discord"}
                                ※ これだけは裏のスレッドから呼ばれます。
                                  画面（Tk）を触らず、すぐ終わる処理にしてください。

    @api.filter("overlay_text")
    def add_emoji(text):
        return "🔥 " + text


--------------------------------------------------------------
 7. 画面に足す
--------------------------------------------------------------

  api.add_panel(build, title=None)
      メイン画面（今日のアプリ別の下）に枠を足します。
      build(frame) には ttk.Frame が渡されるので、その中に部品を置きます。
      テーマを変えたときや、ほかの MOD をオン・オフしたときに
      作り直されるため、build は何度呼ばれてもよいように書き、
      値は部品ではなく変数（や api.data）に持っておいてください。

        from tkinter import ttk

        def setup(api):
            def build(frame):
                ttk.Label(frame, text="こんにちは").pack(anchor="w")
            api.add_panel(build, title="私の MOD")

  api.add_action(text, func)
      設定 → Mods でこの MOD を選んだときに出るボタンを足します。

  api.refresh_panels()   … 枠を作り直します
  api.colors             … テーマの色 {"text", "sub", "bg", "accent", "green", "orange", "red"}
  api.dark               … ダークテーマなら True


--------------------------------------------------------------
 8. そのほかの機能
--------------------------------------------------------------

  api.notify(text, title=None)   Windows の通知を出す（title を省くと MOD の名前）
  api.log(*values)               設定 → Mods のログ欄に書く（print の代わりに）
  api.after(ms, func, *args)     ms ミリ秒後に func を呼ぶ（取り消すときは api.cancel(戻り値)）
                                  くり返したいときは、func の中でもう一度 api.after を呼ぶ
  api.call_soon(func, *args)     別スレッドから、画面のスレッドで func を呼んでもらう
  api.data                       MOD 専用の保存用 dict（起動時に読み込まれる）
  api.save_data()                api.data をファイルに保存する
                                  （%APPDATA%\WorkMonitor\mod_data\<MOD の ID>.json）
  api.config()                   WorkMonitor の設定のコピー（変えても反映されません）
  api.version                    WorkMonitor のバージョン（例: "1.6.0"）
  api.id                         この MOD の ID
  api.mod_dir                    この MOD のフォルダ（フォルダの MOD なら、そのフォルダ）
  api.root                       Tk のメインウィンドウ（ダイアログを出すときの親などに）
  api.app                        WorkMonitor 本体。上級者向けで、中身は予告なく変わります


--------------------------------------------------------------
 9. 守ってほしいこと
--------------------------------------------------------------

  ・setup やイベントの関数は、すぐに終わらせてください。
    time.sleep() や長い処理をすると、アプリの画面が固まります。
    時間のかかる処理（通信など）は threading で別スレッドにして、
    結果を画面に出すときは api.call_soon() を使ってください。
  ・画面（Tk の部品）は、画面のスレッド（イベント・after・call_soon の中）でだけ触ってください。
  ・MOD の中で例外が起きてもアプリは止まりません。エラーは設定 → Mods のログ欄に出ます。
    同じ MOD で 10 回エラーが起きると、その MOD は自動で止まります。
    直してから「再読み込み」を押してください。
  ・記録ファイル（%APPDATA%\WorkMonitor\logs）や設定を書き換える MOD は作らないでください。
    記録が壊れることがあります。
  ・パスワードやアカウントの情報を扱う MOD は作らないでください。


--------------------------------------------------------------
 10. 使えるモジュール
--------------------------------------------------------------

  Python 版（python app.py）で動かしているときは、入っているものは何でも使えます。

  exe 版（配布版）では、アプリに同梱されているものだけ使えます。
    ・tkinter（ttk・messagebox・filedialog・simpledialog・colorchooser）
    ・json, os, re, time, datetime, calendar, math, random, statistics, string,
      csv, threading, urllib.request, urllib.parse, hashlib, uuid, textwrap,
      winsound, zipfile, ctypes など
    ・PIL（Pillow）
  そのほかのライブラリが必要なときは、MOD のフォルダの中に入れて
  from . import ～ で読み込んでください（純粋な Python のものに限ります）。


--------------------------------------------------------------
 11. うまく動かないとき
--------------------------------------------------------------

  ・設定 → Mods で MOD を選ぶと、ログ欄にエラーの内容が出ます。
  ・ファイルを直したら「再読み込み」で読み込み直せます（アプリの再起動は不要）。
  ・MOD のせいでアプリが起動しなくなったときは、次のどちらかをしてください。
      - WorkMonitor.exe --no-mods で起動する（MOD を読み込まないセーフモード）
      - mods フォルダから、その MOD を消す（または名前の先頭に _ を付ける）

  質問や不具合の報告: https://github.com/kaikomziu/WorkMonitor/issues
