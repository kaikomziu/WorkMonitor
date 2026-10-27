# WorkMonitor

**実際に手を動かしている時間だけ**を記録する、Windows 10 / 11 用の作業時間トラッカーです。
キーボードやマウスの操作が止まると記録も止まるので、「アプリを開いたまま放置」した時間は数えません。

## 主な機能

- **入力ベースの計測**：一定時間（初期値 60 秒）操作がないと自動で「休憩中」になります
- **アプリ別の設定**：アプリごとに「作業に数えるか」「カテゴリ」「Discord に出す文言」を決められます
- **ダッシュボード**：日別・カテゴリ別・アプリ別・時間帯別のグラフと表をブラウザで表示します
- **オーバーレイ**：画面の端に小さなタイマーを常に表示します（透明度・大きさ・クリック透過を設定可能）
- **Discord 連携**：プロフィールに「作業中 1:23:45 経過」のように表示します（Rich Presence）
- **タスクトレイ常駐**・Windows 起動時の自動起動・メイン画面の最前面表示

## ダウンロード

[Releases](../../releases) から `WorkMonitor.zip` をダウンロードし、展開した `WorkMonitor.exe` を実行してください。
インストールは不要です。

> 署名のない exe なので、初回は「Windows によって PC が保護されました」と表示されます。
> 「詳細情報」→「実行」で起動できます。

## Discord に表示するには

1. [Discord Developer Portal](https://discord.com/developers/applications) で「New Application」を作成します
   （アプリに付けた名前が「〇〇をプレイ中」として表示されます）
2. 表示された **Application ID** をコピーします
3. WorkMonitor の「設定 → Discord」に貼り付けて保存します
4. PC 版の Discord アプリを起動しておきます（ブラウザ版の Discord では表示されません）

配布する側があらかじめ [core.py](core.py) の `DEFAULT_DISCORD_CLIENT_ID` に ID を入れてビルドしておくと、
利用者は ID を設定しなくても表示できます。

## データの保存先

`%APPDATA%\WorkMonitor` に保存されます。

| ファイル | 内容 |
| --- | --- |
| `logs\YYYY-MM-DD.csv` | 作業の記録（開始・終了時刻・秒数・アプリ・ウィンドウタイトル） |
| `config.json` | 設定 |
| `apps.json` | これまでに使ったアプリの一覧（アプリ別設定の候補） |

記録は PC の中だけに保存し、外部には送信しません。
Discord 連携をオンにした場合だけ、作業中か休憩中かと作業時間が Discord に表示されます。

## ソースから動かす / ビルドする

Python 3.10 以上が必要です。

```bat
pip install -r requirements.txt
python app.py
```

配布用の exe と ZIP は `build.bat` で `dist\` に作られます（PyInstaller を使います）。

コマンドライン版もあります（記録は GUI 版と共通です）。

```bat
python monitor.py            :: 監視だけ行う
python monitor.py report     :: 今日の集計を表示
python monitor.py dashboard  :: ダッシュボードを開く
```

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `app.py` | GUI（メイン画面・設定画面・タスクトレイ） |
| `core.py` | 監視の本体、設定、アプリ別ルール、ログの読み書き |
| `overlay.py` | 常に最前面に出る小さなタイマー |
| `dashboard.py` | グラフ表示用の HTML の生成 |
| `discord_rpc.py` | Discord Rich Presence（外部ライブラリを使わない IPC 実装） |
| `monitor.py` | コマンドライン版 |
| `app_icon.py` | アイコンの描画 |
