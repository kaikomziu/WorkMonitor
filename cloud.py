"""アカウント（Supabase Auth）とクラウド同期

送るのは「日ごと・アプリごとの合計秒数」と目標などの設定だけ。ウィンドウタイトルは送らない。
ログイン情報（トークン）は Windows の DPAPI で暗号化して AppData に保存する。
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import core

SUPABASE_URL = "https://wbzfrhdhfmqxdjheiutl.supabase.co"
# 公開用のキー（ブラウザやアプリに埋め込んでよい種類。データは行レベルのアクセス制限で守られる）
SUPABASE_KEY = "sb_publishable_9v6XNPJ_Tdo4fcwejezQiA_LjUBYohT"
SESSION_PATH = os.path.join(core.DATA_DIR, "session.bin")
FULL_SYNC_DAYS = 120  # ログイン直後や設定変更後に送り直す日数

ERROR_MESSAGES = {
    "invalid login credentials": "メールアドレスかパスワードが違います。",
    "email not confirmed": "メールアドレスの確認が済んでいません。届いた確認メールのリンクを開いてください。",
    "user already registered": "このメールアドレスはすでに登録されています。ログインしてください。",
    "password should be at least": "パスワードは6文字以上にしてください。",
    "unable to validate email address": "メールアドレスの形式が正しくありません。",
    "email rate limit exceeded": "確認メールの送信が多すぎます。しばらく待ってからやり直してください。",
}


class CloudError(Exception):
    pass


# ===== DPAPI（このユーザーだけが復号できる暗号化） =====
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data, protect):
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    src, _keep = _blob(data)
    out = DATA_BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


# ===== 通信 =====
def _http(method, path, body=None, token=None, headers=None):
    url = SUPABASE_URL + path
    h = {"apikey": SUPABASE_KEY, "Content-Type": "application/json",
         "User-Agent": f"{core.APP_NAME}/{core.APP_VERSION}"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    h.update(headers or {})
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            text = res.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8"))
        except ValueError:
            detail = {}
        msg = detail.get("error_description") or detail.get("msg") or detail.get("message") or str(e)
        for key, ja in ERROR_MESSAGES.items():
            if key in msg.lower():
                raise CloudError(ja) from None
        raise CloudError(f"サーバーエラー（{e.code}）: {msg}") from None
    except (urllib.error.URLError, OSError) as e:
        raise CloudError("サーバーにつながりません。インターネット接続を確認してください。") from e


class Cloud:
    """ログイン状態を持ち、期限が近いトークンは自動で更新する（別スレッドから使う）"""

    def __init__(self):
        self.session = self._load()

    # ---- 保存 ----
    def _load(self):
        try:
            with open(SESSION_PATH, "rb") as f:
                return json.loads(_dpapi(f.read(), protect=False).decode("utf-8"))
        except (OSError, ValueError):
            return None

    def _save(self):
        os.makedirs(core.DATA_DIR, exist_ok=True)
        if self.session:
            with open(SESSION_PATH, "wb") as f:
                f.write(_dpapi(json.dumps(self.session).encode("utf-8"), protect=True))
        elif os.path.exists(SESSION_PATH):
            os.remove(SESSION_PATH)

    def _set_session(self, res):
        self.session = {
            "access_token": res["access_token"],
            "refresh_token": res["refresh_token"],
            "expires_at": time.time() + res.get("expires_in", 3600),
            "email": res.get("user", {}).get("email", ""),
            "user_id": res.get("user", {}).get("id", ""),
            "last_sync": (self.session or {}).get("last_sync"),
        }
        self._save()

    # ---- アカウント ----
    @property
    def logged_in(self):
        return bool(self.session)

    @property
    def email(self):
        return (self.session or {}).get("email", "")

    @property
    def last_sync(self):
        return (self.session or {}).get("last_sync")

    def sign_in(self, email, password):
        res = _http("POST", "/auth/v1/token?grant_type=password", {"email": email, "password": password})
        self._set_session(res)

    def sign_up(self, email, password):
        """登録する。確認メールが必要なら False、すぐログインできたら True"""
        q = urllib.parse.urlencode({"redirect_to": core.WEBSITE_URL + "app.html"})
        res = _http("POST", f"/auth/v1/signup?{q}", {"email": email, "password": password})
        if res and res.get("access_token"):
            self._set_session(res)
            return True
        return False

    def sign_out(self):
        if self.session:
            try:
                _http("POST", "/auth/v1/logout", {}, token=self.session["access_token"])
            except CloudError:
                pass  # オフラインでもローカルのログイン情報は消す
        self.session = None
        self._save()

    def _token(self):
        if not self.session:
            raise CloudError("ログインしていません。")
        if time.time() > self.session["expires_at"] - 120:
            try:
                res = _http("POST", "/auth/v1/token?grant_type=refresh_token",
                            {"refresh_token": self.session["refresh_token"]})
            except CloudError as e:
                if "サーバーにつながりません" not in str(e):
                    # 更新できない（別の場所でログアウトした等）ならログアウト扱い
                    self.session = None
                    self._save()
                    raise CloudError("ログインの有効期限が切れました。もう一度ログインしてください。") from None
                raise
            self._set_session(res)
        return self.session["access_token"]

    # ---- 同期 ----
    def sync(self, config, today_by_app=None, days=2):
        """直近 days 日分を送る（today_by_app には記録中の分を含めた今日の値を渡す）"""
        token = self._token()
        today = date.today()
        payload = []
        for i in range(days):
            d = today - timedelta(days=i)
            by_app = today_by_app if (i == 0 and today_by_app is not None) else core.load_day_by_app(d.isoformat())
            rows = _day_rows(config, by_app)
            if rows or i < 2:  # 今日と昨日は空でも送る（消した記録を反映するため）
                payload.append({"day": d.isoformat(), "rows": rows})
        _http("POST", "/rest/v1/rpc/wm_sync_days", {"p_days": payload}, token=token)
        _http("POST", "/rest/v1/wm_profiles", {
            "user_id": self.session["user_id"],
            "daily_goal_min": int(config.get("daily_goal_min", 0)),
            "category_colors": core.category_colors(config),
            "last_sync_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "app_version": core.APP_VERSION,
        }, token=token, headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
        self.session["last_sync"] = time.time()
        self._save()


def _day_rows(config, by_app):
    """アプリ別の秒数 → 送信用の行（作業に数えるアプリだけ。大文字小文字違いはまとめる）"""
    merged = {}
    for app, sec in by_app.items():
        info = core.app_info(config, app)
        if not info["count"] or sec < 1:
            continue
        key = app.lower()
        row = merged.setdefault(key, {"app": key, "name": info["name"], "category": info["category"], "seconds": 0})
        row["seconds"] += int(sec)
    return list(merged.values())
