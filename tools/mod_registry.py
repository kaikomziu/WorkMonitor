"""MOD の審査と公開（GitHub Actions の .github/workflows/mod-review.yml から動かす）

  python tools/mod_registry.py review <結果ファイル>   投稿を受け取って審査し、合格したものを docs/mods に置く
  python tools/mod_registry.py finish <結果ファイル>   （公開を push したあと）審査結果をサーバーに書く
  python tools/mod_registry.py add <ファイル>          運営者が手元から MOD を公開する（作例など）
  python tools/mod_registry.py remove <MOD の名前>     運営者が MOD の公開をやめる

投稿の中身・利用者の情報は公開されるログ（Actions のログ）に出さない。
"""

import base64
import hashlib
import io
import json
import os
import ssl
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mod_review  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS_DIR = os.path.join(ROOT, "docs", "mods")
INDEX_PATH = os.path.join(MODS_DIR, "index.json")
SUPABASE_URL = "https://wbzfrhdhfmqxdjheiutl.supabase.co"
SUPABASE_KEY = "sb_publishable_9v6XNPJ_Tdo4fcwejezQiA_LjUBYohT"
KEEP_VERSIONS = 10
TLS = ssl.create_default_context()
TLS.minimum_version = ssl.TLSVersion.TLSv1_2


def rpc(name, body):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/{name}", data=json.dumps(body).encode(), method="POST",
                                 headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=TLS, timeout=30) as res:
        return json.loads(res.read() or "null")


def secret():
    s = os.environ.get("MOD_REVIEW_SECRET", "").strip()
    if not s:
        sys.exit("MOD_REVIEW_SECRET がありません")
    return s


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ===== 公開の一覧 =====
def load_index():
    try:
        with open(INDEX_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"updated": None, "mods": []}


def save_index(index):
    index["mods"].sort(key=lambda m: m["updated"], reverse=True)
    index["updated"] = now()
    os.makedirs(MODS_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")


def latest_version(index, mod_id):
    m = next((m for m in index["mods"] if m["id"] == mod_id), None)
    return m["version"] if m else None


def published_entry(index, mod_id, version):
    m = next((m for m in index["mods"] if m["id"] == mod_id), None)
    return next((v for v in m["versions"] if v["version"] == version), None) if m else None


def package(result):
    """公開するファイルを作る → (ファイル名, 中身)。フォルダの MOD は検査済みのファイルだけで zip を作り直す"""
    mod_id = result["mod_id"]
    if result["kind"] == "py":
        return f"{mod_id}.py", next(iter(result["files"].values()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(result["files"]):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, result["files"][name])
    return f"{mod_id}.zip", buf.getvalue()


def clean_changes(text):
    """更新内容（投稿者が書いた文）を一覧に載せられる形にする"""
    text = mod_review.HIDDEN_CHARS.sub("", str(text or ""))
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line)[:500]


def publish(index, result, changes=""):
    """docs/mods/files/<id>/<version>/ に置いて一覧に載せる → 公開した版の情報"""
    info = result["info"]
    mod_id, version = result["mod_id"], info["version"]
    name, content = package(result)
    folder = os.path.join(MODS_DIR, "files", mod_id, version)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "wb") as f:
        f.write(content)
    entry = {
        "version": version,
        "file": f"mods/files/{mod_id}/{version}/{name}",
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "published": now(),
        "permissions": result["report"]["permissions"],
        "api": info.get("api", 1),
        "source_sha256": result["report"]["sha256"],   # 投稿されたファイルのハッシュ（同じ投稿の二重公開を防ぐ）
        "changes": clean_changes(changes),
    }
    mod = next((m for m in index["mods"] if m["id"] == mod_id), None)
    if mod is None:
        mod = {"id": mod_id, "versions": []}
        index["mods"].append(mod)
    mod.update({"name": info["name"], "author": info["author"], "description": info["description"],
                "version": version, "updated": entry["published"]})
    mod["versions"] = [entry] + [v for v in mod["versions"] if v["version"] != version][:KEEP_VERSIONS - 1]
    return entry


# ===== 審査 =====
def cmd_review(out_path):
    rows = rpc("wm_mod_review_claim", {"p_secret": secret(), "p_limit": 10}) or []
    print(f"審査する投稿: {len(rows)} 件")
    index = load_index()
    results = []
    batch_owner = {}   # この回の中で、同じ名前の新しい MOD を別の人が出したとき用
    for row in rows:
        data = base64.b64decode(row["file_b64"])
        res = mod_review.review_mod(row["file_name"], data)
        report = res["report"]
        version = res["info"].get("version")
        if res["ok"] and not row["owner_ok"]:
            res["ok"] = False
            report["findings"].append({"level": "block", "file": "", "line": 0,
                                       "message": "この MOD の名前は、ほかの人がすでに使っています。別の名前にしてください。"})
        if res["ok"] and batch_owner.setdefault(row["mod_id"], row["submitter"]) != row["submitter"]:
            res["ok"] = False
            report["findings"].append({"level": "block", "file": "", "line": 0,
                                       "message": "同じ名前の MOD がほぼ同時に投稿されました。別の名前にしてください。"})
        already = published_entry(index, row["mod_id"], version)
        if res["ok"] and already and already.get("source_sha256") == report["sha256"]:
            # 前回の公開のあと結果を書けなかった投稿（同じファイル）なので、合格のまま記録だけする
            report["ok"] = True
            report["published"] = already["file"]
            results.append({"id": row["id"], "status": "approved", "version": version, "report": report})
            continue
        if res["ok"]:
            latest = latest_version(index, row["mod_id"])
            if latest and mod_review.version_key(version) <= mod_review.version_key(latest):
                res["ok"] = False
                report["findings"].append({"level": "block", "file": "", "line": 0,
                                           "message": f"更新するときは、MOD_INFO の version を公開中の {latest} より大きくしてください"
                                                      f"（今は {version}）。"})
        report["ok"] = res["ok"]
        if res["ok"]:
            entry = publish(index, res, row.get("changes", ""))
            report["published"] = entry["file"]
        results.append({"id": row["id"], "status": "approved" if res["ok"] else "rejected",
                        "version": version, "report": report})
    if any(r["status"] == "approved" for r in results):
        save_index(index)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"合格 {sum(r['status'] == 'approved' for r in results)} 件 / 不合格 {sum(r['status'] == 'rejected' for r in results)} 件")


def cmd_finish(out_path):
    try:
        with open(out_path, encoding="utf-8") as f:
            results = json.load(f)
    except OSError:
        print("結果がありません")
        return
    for r in results:
        status = rpc("wm_mod_review_finish", {"p_secret": secret(), "p_id": r["id"], "p_status": r["status"],
                                              "p_version": r["version"], "p_report": r["report"]})
        if status != r["status"]:
            print(f"投稿 {r['id']}: {r['status']} のつもりが {status} になりました")
    print(f"結果を記録しました: {len(results)} 件")


def cmd_add(paths):
    """運営者が手元から公開する（サーバーの投稿は通らない。審査は同じものを行う）"""
    index = load_index()
    for p in paths:
        with open(p, "rb") as f:
            res = mod_review.review_mod(os.path.basename(p), f.read(), bandit=False)
        if not res["ok"]:
            print(f"{p}: 不合格", [x["message"] for x in res["report"]["findings"] if x["level"] == "block"])
            continue
        latest = latest_version(index, res["mod_id"])
        if latest and mod_review.version_key(res["info"]["version"]) <= mod_review.version_key(latest):
            print(f"{p}: すでに {latest} を公開しています")
            continue
        print(f"{p}: 公開しました →", publish(index, res)["file"])
    save_index(index)


def cmd_remove(mod_ids):
    """運営者が公開をやめる（一覧から外し、ファイルも消す。名前は持ち主のまま残る）"""
    import shutil
    index = load_index()
    for mod_id in mod_ids:
        if not mod_review.MOD_ID.match(mod_id):
            print(f"{mod_id}: MOD の名前の形ではありません")
            continue
        before = len(index["mods"])
        index["mods"] = [m for m in index["mods"] if m["id"] != mod_id]
        shutil.rmtree(os.path.join(MODS_DIR, "files", mod_id), ignore_errors=True)
        print(f"{mod_id}: {'公開をやめました' if len(index['mods']) < before else '公開されていません'}")
    save_index(index)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"review": lambda: cmd_review(args[0]), "finish": lambda: cmd_finish(args[0]), "add": lambda: cmd_add(args),
     "remove": lambda: cmd_remove(args)}[cmd]()
