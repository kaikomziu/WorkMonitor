# WorkMonitor

**実際に手を動かしている時間だけ**を記録する、Windows 10 / 11 用の作業時間トラッカーです。
キーボードやマウスの操作が止まると記録も止まるので、「アプリを開いたまま放置」した時間は数えません。

🌐 **ウェブサイト・ダウンロード：https://kaikomziu.github.io/WorkMonitor/**

## 主な機能

- **入力ベースの計測**：一定時間（初期値 60 秒）操作がないと自動で「休憩中」になります
- **1日の目標**：進み具合をバーで表示し、達成したら通知します。連続で達成した日数（🔥）も数えます
- **アプリ別の設定**：アプリごとに「作業に数えるか」「カテゴリ」「Discord に出す文言」を決められます。
  WorkMonitor 自身・Python・Windows の機能（スタートメニュー、検索、設定、エクスプローラーなど）は初期状態で数えません
- **ダッシュボード**：日・週・月ごとに、カテゴリ別・アプリ別・時間帯別のグラフと表をブラウザで表示します。
  週と月は前の期間との比較つきで、週が変わると先週のまとめを通知します
- **アカウントとウェブ表示**：ログインすると記録がクラウドに同期され、[ウェブサイト](https://kaikomziu.github.io/WorkMonitor/app.html)からどの端末でも見られます
- **ライト／ダークテーマ**：アプリ・ダッシュボード・ウェブサイトで切り替えられます
- **アップデート通知**：新しいバージョンが Releases に出たらお知らせします
- **オーバーレイ**：画面の端に小さなタイマーを常に表示します（透明度・大きさ・クリック透過を設定可能）
- **Discord 連携**：プロフィールに「作業中 1:23:45 経過」のように表示します（Rich Presence）
- **タスクトレイ常駐**・Windows 起動時の自動起動・メイン画面の最前面表示
- **MOD（Earo）**：Python で書いた MOD で機能を足せます。ファイルを画面にドラッグ＆ドロップするだけで追加できます

## MOD（Earo）

WorkMonitor には MOD ローダー **Earo** が入っています。MOD はふつうの Python のプログラムで、
`setup(api)` を書くとアプリの起動時に呼ばれ、イベント（作業中になった、目標を達成した など）を受け取ったり、
メイン画面に枠を足したり、オーバーレイや Discord の文字を変えたりできます。

```python
MOD_INFO = {"name": "はじめての MOD", "version": "1.0.0", "author": "あなた"}

def setup(api):
    @api.on("goal_reached")
    def done(goal_min, streak):
        api.notify(f"{streak} 日連続で達成！")
```

- `.py` ファイル・フォルダ（`__init__.py` 入り）・`.zip` をメイン画面か「設定 → Mods」にドラッグ＆ドロップすると追加されます
- 「設定 → Mods」で MOD ごとのオン・オフ、再読み込み、削除、エラーのログの確認ができます
- 「設定 → Mods → 🧩 MOD ストア」から、公式サイトで公開中の MOD をボタン1つで入れたり更新したりできます（[modstore.py](modstore.py)）。
  ダウンロードしたファイルは一覧の SHA-256 と照らし合わせます。ストアから入れた MOD は、自動で更新することもできます（初期はオフ・1日1回）
- MOD の中で例外が起きてもアプリは止まらず、エラーが続いた MOD は自動で止まります。`--no-mods` で起動すると MOD を読み込みません
- 作り方は [mods/modreadme.txt](mods/modreadme.txt)、作例は [mods/examples](mods/examples)（ポモドーロタイマーなど）にあります

> MOD はアプリと同じ権限で動くプログラムです。信頼できる人が作ったものだけ入れてください。

### MOD の配布（公式サイト）

[公式サイトの MOD ページ](https://kaikomziu.github.io/WorkMonitor/mods.html)で、MOD を探してダウンロードしたり、投稿したりできます。

1. ログインした利用者が `.py` / `.zip` を投稿すると、Supabase の `wm_mod_submissions` に入ります（審査待ちは 3 件・1 日 10 件まで）
2. GitHub Actions（[mod-review.yml](.github/workflows/mod-review.yml)、10 分ごと）が合言葉 `MOD_REVIEW_SECRET` で受け取り、
   [tools/mod_review.py](tools/mod_review.py) で自動審査します。投稿されたファイルは**実行せず**、構文を調べるだけです
   - 形式（大きさ、zip のパス・ファイルの種類）、MOD_INFO と setup の有無
   - 危険な書き方（ほかのプログラムの起動、ctypes、eval / exec、ファイルの削除、トークンやパスワードの保存場所、`api.app` など）と bandit の重大な指摘
   - 通信・ファイルの書き込みなどは「この MOD が行うこと」として一覧に表示
3. 合格した MOD は `docs/mods/files/<名前>/<版>/` に置かれ、`docs/mods/index.json` に載って、そのままサイトからダウンロードできます
4. 同じ名前の MOD を更新できるのは最初に公開した人だけです

運営者が手元から公開するとき: `python tools/mod_registry.py add <ファイル>`（作例の hello / pomodoro はこれで公開しています）

## ダウンロード

[ウェブサイト](https://kaikomziu.github.io/WorkMonitor/#download) か [Releases](../../releases/latest) から、どちらかを選んでください。

| 種類 | ファイル | 特徴 |
| --- | --- | --- |
| インストーラー（おすすめ） | `WorkMonitor-Setup.exe` | スタートメニューに登録、Windows の「アプリ」からアンインストール可能、管理者権限は不要 |
| ZIP 版 | `WorkMonitor.zip` | 展開して `WorkMonitor.exe` を実行するだけ。インストール不要 |

> 署名のない exe なので、初回は「Windows によって PC が保護されました」と表示されます。
> 「詳細情報」→「実行」で起動できます。

## アカウントと同期

アプリの「設定 → アカウント」で登録・ログインすると、5分ごとに記録が同期されます。
ウェブサイトの「ログイン」から同じアカウントで入ると、日・週・月のグラフを見られます。

- 送るのは **日ごと・アプリごとの合計時間、カテゴリ、目標** だけです。ウィンドウのタイトルは送りません
- **エンドツーエンド暗号化**：送る前に PC 上で AES-256-GCM で暗号化します（[e2ee.py](e2ee.py)）。
  サーバー（[Supabase](https://supabase.com/)）には暗号文しか置かず、管理者でも中身は読めません。
  ウェブサイトでも復号はブラウザの中だけで行います（WebCrypto、[docs/crypto.js](docs/crypto.js)）
  - データ鍵はランダムな 256bit。パスワードから PBKDF2-HMAC-SHA256（60万回）で作った鍵で包んで保存します
  - 暗号文にはユーザー ID と日付を追加認証データとして結び付け、別の行とのすり替えを検出します
  - パスワードを再設定すると古い鍵は開けないため、クラウドの記録は作り直し（PC の記録から最大120日分を送り直し）になります
- 通信は TLS 1.2 以上のみで、証明書を必ず検証します
- データベースは行レベルのアクセス制限で、本人しか読み書きできません
- ログイン情報とデータ鍵は、この PC のユーザーだけが復号できる形（Windows の DPAPI）で保存します
- ウェブサイトは Content-Security-Policy で読み込み先・通信先を制限し、CDN のスクリプトは SRI で改ざんを検知します
- リリースには改ざん確認用の `SHA256SUMS.txt` を添付します

## Discord に表示するには

1. [Discord Developer Portal](https://discord.com/developers/applications) で「New Application」を作成します
   （アプリに付けた名前が「〇〇をプレイ中」として表示されます）
2. 表示された **Application ID** をコピーします
3. WorkMonitor の「設定 → Discord」に貼り付けて保存します
4. PC 版の Discord アプリを起動しておきます（ブラウザ版の Discord では表示されません）

配布する側があらかじめ [core.py](core.py) の `DEFAULT_DISCORD_CLIENT_ID` に ID を入れてビルドしておくと、
利用者は ID を設定しなくても表示できます。

## データの保存先

`%APPDATA%\WorkMonitor` に保存されます（アンインストールしても残ります）。

| ファイル | 内容 |
| --- | --- |
| `logs\YYYY-MM-DD.csv` | 作業の記録（開始・終了時刻・秒数・アプリ・ウィンドウタイトル） |
| `config.json` | 設定 |
| `apps.json` | これまでに使ったアプリの一覧（アプリ別設定の候補） |
| `session.bin` | ログイン情報（暗号化済み。ログアウトすると消えます） |
| `mods\` | MOD の置き場所（`modreadme.txt` と作例もここにコピーされます） |
| `mod_data\` | MOD が保存したデータ |

外部との通信は次の3つだけです。

- ログイン中かつ同期がオンのとき：上の「アカウントと同期」に書いた内容を暗号化して Supabase に送信
- Discord 連携がオンのとき：作業中か休憩中かと作業時間を Discord に表示
- アップデート確認がオンのとき：1日に1回 GitHub の公開 API に最新版の番号を問い合わせ

## ソースから動かす / ビルドする

Python 3.10 以上が必要です。

```bat
pip install -r requirements.txt
python app.py
```

`build.bat` で `dist\` に exe と ZIP が作られます（PyInstaller を使います）。
[Inno Setup 6](https://jrsoftware.org/isinfo.php) が入っていれば、インストーラー（`installer.iss`）も作ります。

### リリースの手順

1. [core.py](core.py) の `APP_VERSION` を上げてコミット
2. 同じ番号のタグ（例：`v1.2.0`）を push

GitHub Actions（[release.yml](.github/workflows/release.yml)）が exe・ZIP・インストーラーを作り、リリースに添付します。
ウェブサイトのダウンロードボタンは常に最新のリリースを指します。

### コマンドライン版

記録は GUI 版と共通です。

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
| `cloud.py` | アカウント（ログイン・登録）とクラウド同期 |
| `e2ee.py` | 同期データのエンドツーエンド暗号化 |
| `overlay.py` | 常に最前面に出る小さなタイマー |
| `dashboard.py` | グラフ表示用の HTML の生成 |
| `discord_rpc.py` | Discord Rich Presence（外部ライブラリを使わない IPC 実装） |
| `updater.py` | GitHub Releases での新しいバージョンの確認 |
| `earo.py` | MOD ローダー（Earo）と MOD に渡す API |
| `dnd.py` | ウィンドウへのファイルのドラッグ＆ドロップ |
| `mods/` | MOD の作り方（`modreadme.txt`）と作例 |
| `tools/` | 投稿された MOD の自動審査（`mod_review.py`）と公開（`mod_registry.py`） |
| `monitor.py` | コマンドライン版 |
| `app_icon.py` | アイコンの描画 |
| `installer.iss` | インストーラー（Inno Setup） |
| `docs/` | ウェブサイト（GitHub Pages） |

## 利用規約・プライバシーポリシー

アカウントとクラウド同期の利用には、[利用規約](https://kaikomziu.github.io/WorkMonitor/terms.html)と
[プライバシーポリシー](https://kaikomziu.github.io/WorkMonitor/privacy.html)への同意が必要です（登録時にチェック）。
同意した版と日時はサーバーに記録されます。版は `core.TERMS_VERSION` と `docs/common.js` の `termsVersion` で管理し、
変えるとログイン時に改めて同意をお願いします。

アカウントは、ウェブサイトの「記録を見る」ページまたはアプリの「設定 → アカウント」からいつでも削除できます。

運営：かるわか ／ お問い合わせ：[GitHub Issues](https://github.com/kaikomziu/WorkMonitor/issues)

## ライセンス

[MIT License](LICENSE)
