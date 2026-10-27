"""エンドツーエンド暗号化（クラウドに送るデータの暗号化）

- データ鍵（DEK）: ランダムな 256bit。記録の暗号化に使う
- 鍵の保管: パスワードから PBKDF2-HMAC-SHA256（60万回）で作った鍵（KEK）で DEK を AES-256-GCM 暗号化して保存
- 記録: AES-256-GCM。追加認証データ（AAD）にユーザー ID と日付を入れ、他人や別の日の暗号文との
  すり替えを検出する
サーバーに置くのは暗号文・ソルト・回数だけ。パスワードと鍵はサーバーに渡らない。
ウェブサイト（docs/app.js）は WebCrypto で同じ形式を読み書きする。
"""

import base64
import hashlib
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KDF_ITERATIONS = 600_000   # OWASP の推奨値（PBKDF2-HMAC-SHA256）
NONCE_SIZE = 12


class DecryptError(Exception):
    pass


def b64e(data):
    return base64.b64encode(data).decode("ascii")


def b64d(text):
    return base64.b64decode(text)


# ===== AAD（何の暗号文かを暗号に結び付ける） =====
def aad_key(user_id):
    return f"wm:{user_id}:key".encode()


def aad_day(user_id, day):
    return f"wm:{user_id}:day:{day}".encode()


def aad_settings(user_id):
    return f"wm:{user_id}:settings".encode()


# ===== 基本操作 =====
def encrypt(key, plaintext, aad):
    """→ base64(nonce + 暗号文 + 認証タグ)。nonce は毎回ランダム"""
    nonce = os.urandom(NONCE_SIZE)
    return b64e(nonce + AESGCM(key).encrypt(nonce, plaintext, aad))


def decrypt(key, token, aad):
    try:
        raw = b64d(token)
        return AESGCM(key).decrypt(raw[:NONCE_SIZE], raw[NONCE_SIZE:], aad)
    except (InvalidTag, ValueError) as e:
        raise DecryptError("復号できませんでした（鍵が違うか、データが改ざんされています）") from e


def encrypt_json(key, obj, aad):
    return encrypt(key, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), aad)


def decrypt_json(key, token, aad):
    return json.loads(decrypt(key, token, aad).decode("utf-8"))


# ===== 鍵の保管庫 =====
def derive_kek(password, salt, iterations):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)


def new_vault(password, user_id):
    """新しいデータ鍵を作り、パスワードで包む → (保存用の dict, データ鍵)"""
    dek = os.urandom(32)
    salt = os.urandom(16)
    kek = derive_kek(password, salt, KDF_ITERATIONS)
    vault = {
        "kdf_salt": b64e(salt),
        "kdf_iterations": KDF_ITERATIONS,
        "wrapped_key": encrypt(kek, dek, aad_key(user_id)),
    }
    return vault, dek


def unwrap(password, user_id, vault):
    """パスワードでデータ鍵を取り出す。パスワードが変わっていると DecryptError"""
    kek = derive_kek(password, b64d(vault["kdf_salt"]), int(vault["kdf_iterations"]))
    dek = decrypt(kek, vault["wrapped_key"], aad_key(user_id))
    if len(dek) != 32:
        raise DecryptError("鍵の形式が正しくありません")
    return dek
