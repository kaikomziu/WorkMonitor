"""アカウント（Supabase Auth）とクラウド同期

- 通信は TLS 1.2 以上のみ（証明書は必ず検証）
- 送る記録（日ごと・アプリごとの合計秒数、カテゴリ、目標）は e2ee.py で暗号化してから送る。
  サーバーには暗号文しか置かれず、ウィンドウタイトルはそもそも送らない
- ログイン情報とデータ鍵は Windows の DPAPI（このユーザーだけが復号できる）で暗号化して AppData に保存
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import core
import e2ee

SUPABASE_URL = "https://wbzfrhdhfmqxdjheiutl.supabase.co"
# 公開用のキー（ブラウザやアプリに埋め込んでよい種類。データは行レベルのアクセス制限と E2EE で守る）
SUPABASE_KEY = "sb_publishable_9v6XNPJ_Tdo4fcwejezQiA_LjUBYohT"
SESSION_PATH = os.path.join(core.DATA_DIR, "session.bin")
DPAPI_ENTROPY = b"WorkMonitor/session/v2"  # このアプリ専用の追加の鍵材料
FULL_SYNC_DAYS = 120  # ログイン直後や設定変更後に送り直す日数
MIN_PASSWORD_LENGTH = 8

# TLS 1.2 未満は使わない。証明書とホスト名は必ず検証する（create_default_context の既定）
TLS_CONTEXT = ssl.create_default_context()
TLS_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2

ERROR_MESSAGES = {
    "invalid login credentials": "メールアドレスかパスワードが違います。",
    "email not confirmed": "メールアドレスの確認が済んでいません。届いた確認メールのリンクを開いてください。",
    "user already registered": "このメールアドレスはすでに登録されています。ログインしてください。",
    "password should be at least": f"パスワードは{MIN_PASSWORD_LENGTH}文字以上にしてください。",
    "unable to validate email address": "メールアドレスの形式が正しくありません。",
    "email rate limit exceeded": "確認メールの送信が多すぎます。しばらく待ってからやり直してください。",
    "pwned": "このパスワードは過去に流出したことがあるため使えません。別のパスワードにしてください。",
}


class CloudError(Exception):
    pass


# ===== DPAPI（このユーザーだけが復号できる暗号化） =====
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data, protect, entropy=None):
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    src, _keep = _blob(data)
    ent, _keep2 = _blob(entropy) if entropy else (None, None)
    out = DATA_BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    if not fn(ctypes.byref(src), None, ctypes.byref(ent) if ent else None, None, None,
              CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
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
        with urllib.request.urlopen(req, timeout=20, context=TLS_CONTEXT) as res:
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
    except ssl.SSLError as e:
        raise CloudError("安全な接続を確立できませんでした（証明書を確認できません）。") from e
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise CloudError("安全な接続を確立できませんでした（証明書を確認できません）。") from e
        raise CloudError("サーバーにつながりません。インターネット接続を確認してください。") from e


class Cloud:
    """ログイン状態とデータ鍵を持ち、期限が近いトークンは自動で更新する（別スレッドから使う）"""

    def __init__(self):
        self.notice = ""   # 画面に出したいお知らせ（再ログインが必要、など）
        self.session = self._load()

    # ---- 保存 ----
    def _load(self):
        try:
            with open(SESSION_PATH, "rb") as f:
                raw = f.read()
        except OSError:
            return None
        try:
            session = json.loads(_dpapi(raw, protect=False, entropy=DPAPI_ENTROPY).decode("utf-8"))
        except (OSError, ValueError):
            session = None
        if not session or not session.get("dek"):
            # 暗号化に対応する前のログイン情報。鍵を作るにはパスワードが必要なのでログインし直してもらう
            self.notice = "記録の暗号化に対応したため、もう一度ログインしてください。"
            try:
                os.remove(SESSION_PATH)
            except OSError:
                pass
            return None
        return session

    def _save(self):
        os.makedirs(core.DATA_DIR, exist_ok=True)
        if self.session:
            tmp = SESSION_PATH + ".tmp"
            with open(tmp, "wb") as f:
                f.write(_dpapi(json.dumps(self.session).encode("utf-8"), protect=True, entropy=DPAPI_ENTROPY))
            os.replace(tmp, SESSION_PATH)
        elif os.path.exists(SESSION_PATH):
            os.remove(SESSION_PATH)

    def _set_tokens(self, res):
        self.session = dict(self.session or {})
        self.session.update({
            "access_token": res["access_token"],
            "refresh_token": res["refresh_token"],
            "expires_at": time.time() + res.get("expires_in", 3600),
        })
        if res.get("user"):
            self.session["email"] = res["user"].get("email", "")
            self.session["user_id"] = res["user"].get("id", "")

    def _clear(self, notice=""):
        self.session = None
        self.notice = notice
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
        self.session = None
        self._set_tokens(res)
        try:
            self._open_vault(password)
        except Exception:
            self.session = None   # 鍵が用意できなければログインしなかったことにする
            raise
        self.notice = ""
        self._save()

    def sign_up(self, email, password):
        """登録する。確認メールが必要なら False、すぐログインできたら True"""
        if len(password) < MIN_PASSWORD_LENGTH:
            raise CloudError(f"パスワードは{MIN_PASSWORD_LENGTH}文字以上にしてください。")
        q = urllib.parse.urlencode({"redirect_to": core.WEBSITE_URL + "app.html"})
        res = _http("POST", f"/auth/v1/signup?{q}", {"email": email, "password": password})
        if res and res.get("access_token"):
            self.session = None
            self._set_tokens(res)
            self._open_vault(password)
            self._save()
            return True
        return False   # 確認メールのリンクを開いたあと、ログインしたときに鍵を作る

    def sign_out(self):
        if self.session:
            try:
                _http("POST", "/auth/v1/logout", {}, token=self.session["access_token"])
            except CloudError:
                pass  # オフラインでもローカルのログイン情報と鍵は消す
        self._clear()

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
                    self._clear("ログインの有効期限が切れました。もう一度ログインしてください。")
                    raise CloudError(self.notice) from None
                raise
            self._set_tokens(res)
            self._save()
        return self.session["access_token"]

    # ---- 鍵の保管庫 ----
    def _get_vault(self, token):
        uid = self.session["user_id"]
        rows = _http("GET", f"/rest/v1/wm_profiles?select=kdf_salt,kdf_iterations,wrapped_key&user_id=eq.{uid}",
                     token=token)
        return rows[0] if rows and rows[0].get("wrapped_key") else None

    def _put_profile(self, token, fields):
        _http("POST", "/rest/v1/wm_profiles", dict(fields, user_id=self.session["user_id"]), token=token,
              headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def _open_vault(self, password):
        """データ鍵を取り出す。まだ無ければ作る。パスワードが変わって開けなければ作り直す"""
        token = self.session["access_token"]
        uid = self.session["user_id"]
        vault = self._get_vault(token)
        self.session["vault_reset"] = False
        if vault:
            try:
                dek = e2ee.unwrap(password, uid, vault)
            except e2ee.DecryptError:
                # パスワード再設定などで鍵が開けない → クラウドの古い暗号文は読めないので消して作り直す
                # （PC の記録から最大 FULL_SYNC_DAYS 日分を送り直す）
                _http("DELETE", f"/rest/v1/wm_days?user_id=eq.{uid}", token=token)
                vault = None
                self.session["vault_reset"] = True
        if not vault:
            vault, dek = e2ee.new_vault(password, uid)
            self._put_profile(token, dict(vault, settings_payload=None))
        self.session["dek"] = e2ee.b64e(dek)
        self.session["wrapped_key"] = vault["wrapped_key"]

    # ---- 同期 ----
    def sync(self, config, today_by_app=None, days=2):
        """直近 days 日分を暗号化して送る（today_by_app には記録中の分を含めた今日の値を渡す）"""
        token = self._token()
        uid = self.session["user_id"]
        # 別の場所でパスワードが変わり鍵が作り直されていたら、古い鍵では送らない
        vault = self._get_vault(token)
        if not vault or vault["wrapped_key"] != self.session.get("wrapped_key"):
            self._clear("パスワードが変更されたため、もう一度ログインしてください。")
            raise CloudError(self.notice)
        dek = e2ee.b64d(self.session["dek"])

        today = date.today()
        payload = []
        for i in range(days):
            d = today - timedelta(days=i)
            by_app = today_by_app if (i == 0 and today_by_app is not None) else core.load_day_by_app(d.isoformat())
            rows = _day_rows(config, by_app)
            if rows or i < 2:  # 今日と昨日は空でも送る（消した記録を反映するため）
                payload.append({"day": d.isoformat(),
                                "payload": e2ee.encrypt_json(dek, rows, e2ee.aad_day(uid, d.isoformat()))})
        # 1回の送信が大きくなりすぎないよう分けて送る
        for i in range(0, len(payload), 60):
            _http("POST", "/rest/v1/rpc/wm_put_days", {"p_days": payload[i:i + 60]}, token=token)
        settings = {"daily_goal_min": int(config.get("daily_goal_min", 0)),
                    "category_colors": core.category_colors(config)}
        self._put_profile(token, {
            "settings_payload": e2ee.encrypt_json(dek, settings, e2ee.aad_settings(uid)),
            "last_sync_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "app_version": core.APP_VERSION,
        })
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
