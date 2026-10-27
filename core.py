"""作業監視の本体（GUI / CLI 共通）

キーボード／マウスの入力があった時間だけを「作業時間」として記録する。
ウィンドウを開いたまま放置している時間はカウントしない。
アプリごとに「作業に数えるか」「カテゴリ」「Discord の表示文言」を設定できる。
"""

import csv
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

from discord_rpc import DiscordPresence

APP_NAME = "WorkMonitor"
APP_VERSION = "1.4.0"
GITHUB_REPO = "kaikomziu/WorkMonitor"  # アップデート確認に使う
WEBSITE_URL = "https://kaikomziu.github.io/WorkMonitor/"
TERMS_URL = WEBSITE_URL + "terms.html"
PRIVACY_URL = WEBSITE_URL + "privacy.html"
# 利用規約・プライバシーポリシーの版（変えると、ログイン時にもう一度同意をお願いする）。docs/common.js と同じ値
TERMS_VERSION = "2026-10-27"

# 配布する前に、自分で作った Discord アプリの Application ID をここに入れておくと
# 利用者は設定なしで Discord 表示が使える（空なら利用者が設定画面で入力する）
DEFAULT_DISCORD_CLIENT_ID = ""

POLL_INTERVAL_SEC = 1        # 監視間隔
MAX_SEGMENT_SEC = 300        # 長い区間はこの秒数ごとに書き出す（異常終了対策）
UNCATEGORIZED = "未分類"

DEFAULT_CONFIG = {
    "idle_threshold_sec": 60,     # この秒数入力が無ければ「放置」とみなす
    "daily_goal_min": 180,        # 1日の目標（分）。0 なら目標なし
    "autostart": False,
    "theme": "system",            # "system"（Windows に合わせる） / "light" / "dark"
    "cloud_sync": True,           # ログイン中は記録をクラウドに同期する
    "update_check": True,         # 起動時に GitHub で新しいバージョンを確認
    # 通知を一度だけ出すための記録
    "notified": {"goal_date": "", "week": "", "update_version": ""},
    "always_on_top": False,       # メイン画面を常に最前面に表示
    "discord_enabled": True,
    "discord_client_id": "",
    "discord_show_app": False,
    "overlay": {
        "enabled": False,
        "opacity": 0.85,
        "size": "中",
        "click_through": False,   # マウス操作を後ろのウィンドウに通す
        "show_app": True,
        "x": None,
        "y": None,
    },
    # 作業時間に含めるアプリの決め方
    #   "all"      … 「数えない」にしたアプリ以外はすべて数える
    #   "selected" … included_apps に入れたアプリだけを数える
    "count_mode": "all",
    "included_apps": [],          # exe 名（小文字）
    # キーは exe 名（小文字）。値は name / category / count / discord
    "app_rules": {},
}

# よく使うアプリの表示名とカテゴリの初期値
KNOWN_APPS = {
    "code.exe": ("VS Code", "開発"),
    "cursor.exe": ("Cursor", "開発"),
    "devenv.exe": ("Visual Studio", "開発"),
    "pycharm64.exe": ("PyCharm", "開発"),
    "idea64.exe": ("IntelliJ IDEA", "開発"),
    "windowsterminal.exe": ("ターミナル", "開発"),
    "powershell.exe": ("PowerShell", "開発"),
    "pwsh.exe": ("PowerShell", "開発"),
    "cmd.exe": ("コマンドプロンプト", "開発"),
    "unity.exe": ("Unity", "開発"),
    "robloxstudiobeta.exe": ("Roblox Studio", "開発"),
    "claude.exe": ("Claude", "開発"),
    "chrome.exe": ("Chrome", "ブラウザ"),
    "msedge.exe": ("Edge", "ブラウザ"),
    "firefox.exe": ("Firefox", "ブラウザ"),
    "brave.exe": ("Brave", "ブラウザ"),
    "vivaldi.exe": ("Vivaldi", "ブラウザ"),
    "opera.exe": ("Opera", "ブラウザ"),
    "arc.exe": ("Arc", "ブラウザ"),
    "floorp.exe": ("Floorp", "ブラウザ"),
    "zen.exe": ("Zen", "ブラウザ"),
    "excel.exe": ("Excel", "資料作成"),
    "winword.exe": ("Word", "資料作成"),
    "powerpnt.exe": ("PowerPoint", "資料作成"),
    "notion.exe": ("Notion", "資料作成"),
    "obsidian.exe": ("Obsidian", "資料作成"),
    "photoshop.exe": ("Photoshop", "デザイン"),
    "illustrator.exe": ("Illustrator", "デザイン"),
    "clipstudiopaint.exe": ("CLIP STUDIO PAINT", "デザイン"),
    "figma.exe": ("Figma", "デザイン"),
    "blender.exe": ("Blender", "デザイン"),
    "discord.exe": ("Discord", "コミュニケーション"),
    "slack.exe": ("Slack", "コミュニケーション"),
    "ms-teams.exe": ("Teams", "コミュニケーション"),
    "zoom.exe": ("Zoom", "コミュニケーション"),
    "line.exe": ("LINE", "コミュニケーション"),
}
SYSTEM_CATEGORY = "Windows"
DEFAULT_CATEGORIES = ["開発", "ブラウザ", "資料作成", "デザイン", "コミュニケーション", SYSTEM_CATEGORY, "その他"]

# 初期状態で「作業に数えない」アプリ（このアプリ自身・Python・Windows の機能）
NOT_COUNTED_APPS = {
    "workmonitor.exe": ("WorkMonitor", "その他"),
    "python.exe": ("Python", "その他"),
    "pythonw.exe": ("Python", "その他"),
    "py.exe": ("Python", "その他"),
    "(なし)": ("（ウィンドウなし）", SYSTEM_CATEGORY),
    "(不明)": ("（不明なアプリ）", SYSTEM_CATEGORY),
    "explorer.exe": ("エクスプローラー・デスクトップ", SYSTEM_CATEGORY),
    "searchhost.exe": ("Windows 検索", SYSTEM_CATEGORY),
    "searchapp.exe": ("Windows 検索", SYSTEM_CATEGORY),
    "startmenuexperiencehost.exe": ("スタートメニュー", SYSTEM_CATEGORY),
    "shellexperiencehost.exe": ("通知・クイック設定", SYSTEM_CATEGORY),
    "shellhost.exe": ("クイック設定", SYSTEM_CATEGORY),
    "textinputhost.exe": ("文字入力（IME）", SYSTEM_CATEGORY),
    "ctfmon.exe": ("文字入力（IME）", SYSTEM_CATEGORY),
    "lockapp.exe": ("ロック画面", SYSTEM_CATEGORY),
    "logonui.exe": ("サインイン画面", SYSTEM_CATEGORY),
    "consent.exe": ("ユーザーアカウント制御", SYSTEM_CATEGORY),
    "credentialuibroker.exe": ("資格情報の入力", SYSTEM_CATEGORY),
    "applicationframehost.exe": ("Windows アプリ", SYSTEM_CATEGORY),
    "systemsettings.exe": ("設定", SYSTEM_CATEGORY),
    "taskmgr.exe": ("タスクマネージャー", SYSTEM_CATEGORY),
    "control.exe": ("コントロールパネル", SYSTEM_CATEGORY),
    "mmc.exe": ("管理ツール", SYSTEM_CATEGORY),
    "rundll32.exe": ("Windows の機能", SYSTEM_CATEGORY),
    "dllhost.exe": ("Windows の機能", SYSTEM_CATEGORY),
    "openwith.exe": ("プログラムから開く", SYSTEM_CATEGORY),
    "pickerhost.exe": ("ファイルの選択", SYSTEM_CATEGORY),
    "widgets.exe": ("ウィジェット", SYSTEM_CATEGORY),
    "screenclippinghost.exe": ("画面の切り取り", SYSTEM_CATEGORY),
    "securityhealthsystray.exe": ("Windows セキュリティ", SYSTEM_CATEGORY),
    "smartscreen.exe": ("SmartScreen", SYSTEM_CATEGORY),
    "osk.exe": ("スクリーンキーボード", SYSTEM_CATEGORY),
}

# データはユーザーごとの AppData に置く（exe を Program Files に置いても書き込めるように）
DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
LOG_DIR = os.path.join(DATA_DIR, "logs")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
SEEN_APPS_PATH = os.path.join(DATA_DIR, "apps.json")


# ===== 設定 =====
def load_config():
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # 深いコピー
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        # 入れ子の設定は項目ごとに上書き（新しいバージョンで増えた項目に初期値を残す）
        nested = {k: saved.pop(k, {}) for k in ("overlay", "notified")}
        config.update(saved)
        for k, v in nested.items():
            config[k].update(v)
    except (OSError, ValueError):
        pass
    return config


def save_config(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def effective_client_id(config):
    return (config.get("discord_client_id") or DEFAULT_DISCORD_CLIENT_ID).strip()


BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "vivaldi.exe", "opera.exe",
            "arc.exe", "floorp.exe", "zen.exe"}
# ブラウザがタイトルの最後に付ける名前と、Edge のプロファイル名
BROWSER_SUFFIXES = ("google chrome", "microsoft edge", "mozilla firefox", "firefox", "brave", "vivaldi",
                    "opera", "arc", "floorp", "zen browser", "個人", "personal", "職場", "work")
TITLE_SEPARATOR = re.compile(r"\s+[-–—]\s+|\s*[|｜]\s*")
UNREAD_PREFIX = re.compile(r"^(\(\d+\+?\)|[●*•])\s*")
GITHUB_REPO_TITLE = re.compile(r"^(GitHub\s*-\s*)?[\w.-]+/[\w.-]+(:|\s|$)")  # 「owner/repo: 説明」
ON_SITE_SUFFIX = re.compile(r"\s+on\s+(Scratch|X|Twitter|Bluesky)$")


def window_label(app, title):
    """集計で使う「サイト・ウィンドウ名」

    ブラウザはページごとにタイトルが変わるので、最後の区切りの後ろ（サイト名）でまとめる。
    例: 「(30) 人生『1レーン』 - YouTube - Vivaldi」→「YouTube」
    ほかのアプリは未読数や未保存の印だけ取り除く。
    """
    title = UNREAD_PREFIX.sub("", title.strip())
    if app.lower() not in BROWSERS:
        return title
    parts = [p for p in TITLE_SEPARATOR.split(title) if p]
    while len(parts) > 1 and parts[-1].strip().lower() in BROWSER_SUFFIXES:
        parts.pop()
    if not parts or parts[0].strip().lower() in BROWSER_SUFFIXES:
        return "（新しいタブ）"
    if GITHUB_REPO_TITLE.match(parts[0]):
        return "GitHub"
    site = UNREAD_PREFIX.sub("", parts[-1].strip())
    m = ON_SITE_SUFFIX.search(site)   # 「作品名 on Scratch」の形
    return m.group(1) if m else site


def app_info(config, app):
    """アプリのルール（初期値 → ユーザー設定の順に上書き）"""
    key = app.lower()
    if key in NOT_COUNTED_APPS:
        (name, category), count = NOT_COUNTED_APPS[key], False
    else:
        (name, category), count = KNOWN_APPS.get(key, (os.path.splitext(app)[0], UNCATEGORIZED)), True
    info = {"name": name, "category": category, "count": count, "discord": ""}
    info.update(config.get("app_rules", {}).get(key, {}))
    if config.get("count_mode") == "selected":
        info["count"] = key in config.get("included_apps", [])
    return info


def all_categories(config):
    cats = list(DEFAULT_CATEGORIES)
    for rule in config.get("app_rules", {}).values():
        c = rule.get("category")
        if c and c not in cats and c != UNCATEGORIZED:
            cats.append(c)
    return cats + [UNCATEGORIZED]


CATEGORY_PALETTE = ["#4f6bed", "#22a06b", "#e2a03f", "#d9534f", "#8e6bd8", "#2bb3c0", "#e57fb0"]
UNCATEGORIZED_COLOR = "#8a919c"


def category_colors(config):
    """カテゴリ → 色（アプリ画面とダッシュボードで同じ色にする）"""
    colors = {}
    for i, c in enumerate(all_categories(config)[:-1]):
        colors[c] = CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
    colors[UNCATEGORIZED] = UNCATEGORIZED_COLOR
    return colors


def recent_apps(days=30):
    """アプリ別設定の候補: 見かけたアプリ + 最近の記録に出てくるアプリ"""
    apps = set(load_seen_apps())
    for path in sorted(glob.glob(os.path.join(LOG_DIR, "????-??-??.csv")))[-days:]:
        with open(path, encoding="utf-8-sig") as f:
            apps.update(r["app"] for r in csv.DictReader(f))
    return apps


# ===== 見かけたアプリの一覧（アプリ別設定の候補に使う） =====
def load_seen_apps():
    try:
        with open(SEEN_APPS_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_seen_apps(apps):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SEEN_APPS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(apps), f, ensure_ascii=False)


# ===== Windows API =====
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


def get_idle_seconds():
    """最後のキーボード／マウス入力からの経過秒数"""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # GetTickCount は 32bit で約49日で一周するのでマスクして差分を取る
    tick = kernel32.GetTickCount() & 0xFFFFFFFF
    return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0


def get_foreground_app():
    """前面ウィンドウの (プロセス名, ウィンドウタイトル) を返す"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("(なし)", "")

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = "(不明)"
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if h:
        size = wt.DWORD(1024)
        pbuf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h, 0, pbuf, ctypes.byref(size)):
            name = os.path.basename(pbuf.value)
        kernel32.CloseHandle(h)
    return (name, title)


# ===== ログ =====
def log_path(date_str):
    return os.path.join(LOG_DIR, f"{date_str}.csv")


def write_segment(start, end, app, title):
    """作業区間を日付ごとの CSV に追記する"""
    sec = end - start
    if sec < 1:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    path = log_path(datetime.fromtimestamp(start).strftime("%Y-%m-%d"))
    new_file = not os.path.exists(path)
    # Excel で文字化けしないよう BOM 付き UTF-8
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["start", "end", "seconds", "app", "title"])
        w.writerow([
            datetime.fromtimestamp(start).strftime("%H:%M:%S"),
            datetime.fromtimestamp(end).strftime("%H:%M:%S"),
            round(sec),
            app,
            title,
        ])


def load_day_by_app(date_str):
    """指定日の CSV に記録済みのアプリ別秒数"""
    by_app = defaultdict(float)
    path = log_path(date_str)
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                by_app[r["app"]] += float(r["seconds"])
    return by_app


def counted_seconds(config, by_app):
    """「作業に数えない」アプリを除いた合計"""
    return sum(sec for app, sec in by_app.items() if app_info(config, app)["count"])


def day_total(config, day):
    """指定日（date）の作業時間（秒）"""
    return counted_seconds(config, load_day_by_app(day.strftime("%Y-%m-%d")))


def goal_streak_before(config, today):
    """昨日までに目標を連続で達成した日数（今日の分は呼び出し側で足す）"""
    goal = config.get("daily_goal_min", 0) * 60
    if goal <= 0:
        return 0
    streak = 0
    day = today - timedelta(days=1)
    for _ in range(365):
        if day_total(config, day) < goal:
            break
        streak += 1
        day -= timedelta(days=1)
    return streak


def week_total(config, monday):
    return sum(day_total(config, monday + timedelta(days=i)) for i in range(7))


def last_week_summary(config, today):
    """(先週の合計秒, 先々週の合計秒)"""
    this_monday = today - timedelta(days=today.weekday())
    last = this_monday - timedelta(days=7)
    return week_total(config, last), week_total(config, last - timedelta(days=7))


# ===== 監視 =====
class Monitor:
    """別スレッドで動く監視ループ。GUI は state / app / today_sec などを読むだけ

    state: "working"（作業中） / "idle"（放置） / "excluded"（数えないアプリを使用中）
    """

    def __init__(self, config):
        self.config = config
        self.state = "idle"
        self.app = ""
        self.today_sec = 0.0
        self.today_by_app = {}
        self.seen_apps = load_seen_apps()
        self.presence = None
        self._presence_key = None
        self._stop = threading.Event()
        self._thread = None

    @property
    def working(self):
        return self.state == "working"

    @property
    def discord_status(self):
        if not self.config.get("discord_enabled"):
            return "オフ"
        if not effective_client_id(self.config):
            return "未設定（設定 → Discord で Application ID を入力）"
        return self.presence.status if self.presence else "準備中"

    def today_by_name(self):
        """今日のアプリ別秒数（表示名でまとめる。作業に数えるアプリのみ）"""
        result = defaultdict(float)
        for app, sec in list(self.today_by_app.items()):
            info = app_info(self.config, app)
            if info["count"]:
                result[info["name"]] += sec
        return dict(result)

    def today_by_category(self):
        """今日のカテゴリ別秒数（作業に数えるアプリのみ）"""
        result = defaultdict(float)
        for app, sec in list(self.today_by_app.items()):
            info = app_info(self.config, app)
            if info["count"]:
                result[info["category"]] += sec
        return dict(result)

    def apply_config(self, config):
        # Discord 接続の作り直しは監視スレッド側で行う
        self.config = config

    def start(self):
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _sync_presence(self):
        """設定が変わっていたら Discord 接続を作り直す"""
        cid = effective_client_id(self.config)
        key = cid if self.config.get("discord_enabled") and cid else None
        if key == self._presence_key:
            return
        if self.presence:
            self.presence.close()
            self.presence = None
        if key:
            self.presence = DiscordPresence(key)
        self._presence_key = key

    def _discord_text(self, info):
        if info["discord"]:
            return info["discord"]
        if self.config.get("discord_show_app"):
            return f"作業中: {info['name']}"
        return "作業中"

    def run(self):
        seg = None  # 現在の作業区間: dict(start, end, app, title)
        today = datetime.now().strftime("%Y-%m-%d")
        done_by_app = load_day_by_app(today)  # 今日すでに書き出した秒数

        def close():
            nonlocal seg
            if seg:
                write_segment(seg["start"], seg["end"], seg["app"], seg["title"])
                if datetime.fromtimestamp(seg["start"]).strftime("%Y-%m-%d") == today:
                    done_by_app[seg["app"]] += max(0, round(seg["end"] - seg["start"]))
                seg = None

        try:
            while not self._stop.is_set():
                config = self.config
                threshold = config.get("idle_threshold_sec", 60)
                now = time.time()
                idle = get_idle_seconds()
                last_input = now - idle
                app, title = get_foreground_app()
                info = app_info(config, app)

                if app not in self.seen_apps and app not in ("(なし)", "(不明)"):
                    self.seen_apps.add(app)
                    save_seen_apps(self.seen_apps)

                if idle >= threshold:
                    state = "idle"
                    # 放置中: 区間の終わりを「最後に操作した時刻」まで切り詰めて閉じる
                    if seg:
                        seg["end"] = max(seg["start"], min(seg["end"], last_input))
                        close()
                elif not info["count"]:
                    state = "excluded"
                    close()
                else:
                    state = "working"
                    if seg and (seg["app"], seg["title"]) != (app, title):
                        close()
                    # 日付をまたいだら区間を分ける
                    if seg and datetime.fromtimestamp(seg["start"]).date() != datetime.fromtimestamp(now).date():
                        close()
                    if seg is None:
                        seg = {"start": now, "end": now, "app": app, "title": title}
                    seg["end"] = now
                    if seg["end"] - seg["start"] >= MAX_SEGMENT_SEC:
                        close()

                # 日付が変わったら今日の合計をリセット
                if datetime.now().strftime("%Y-%m-%d") != today:
                    today = datetime.now().strftime("%Y-%m-%d")
                    done_by_app = load_day_by_app(today)

                by_app = dict(done_by_app)
                if seg:
                    by_app[seg["app"]] = by_app.get(seg["app"], 0) + (seg["end"] - seg["start"])
                self.today_by_app = by_app
                self.today_sec = counted_seconds(config, by_app)
                self.state = state
                self.app = app

                self._sync_presence()
                if self.presence:
                    self.presence.update(self.working, self.today_sec, self._discord_text(info))

                self._stop.wait(POLL_INTERVAL_SEC)
        finally:
            close()
            if self.presence:
                self.presence.close()
