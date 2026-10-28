"""MOD の自動審査（GitHub Actions で動かす）

投稿されたファイルは実行しない。中身を読んで構文（ast）を調べるだけ。
- 形式: .py か .zip か、大きさ、zip の中のパス・ファイルの種類・構成
- 内容: Python として正しいか、MOD_INFO と setup があるか
- 安全: 危険な処理（ほかのプログラムの実行、Windows の機能の直接呼び出し、組み立てたコードの実行、
        ファイルの削除、ブラウザのパスワードやトークンなどの読み取り、WorkMonitor の内部への干渉など）
        を使っていないか。bandit（Python 向けの検査ツール）があれば、その重大な指摘も不合格にする
- 通信・ファイルの書き込みなど、問題ではないが利用者が知っておくべきことは「この MOD が行うこと」として公開する

自動審査は既知の危険な書き方を見つけるためのもので、安全を保証するものではない。
"""

import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

MOD_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
VERSION = re.compile(r"^\d{1,4}(\.\d{1,4}){0,3}$")
MAX_UPLOAD = 512 * 1024
MAX_FILES = 50
MAX_FILE = 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024
MAX_LINE = 2000
MAX_STRING = 5000
API_VERSION = 1
ALLOWED_EXT = {".py", ".txt", ".md", ".json", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".wav"}

# ---- 使えないモジュール（理由） ----
_NATIVE = "Windows の機能やメモリを直接操作できるため"
_EXEC = "ほかのプログラムを起動できるため"
_DYN = "外から持ってきたコードを実行できるため"
_INPUT = "キー入力やマウスを監視・操作できるため"
_INTERNAL = "WorkMonitor の内部（アカウント・暗号鍵など）を直接触れるため。api を使ってください"
BLOCK_MODULES = {
    "subprocess": _EXEC, "multiprocessing": _EXEC, "pty": _EXEC, "asyncio": _EXEC + "（asyncio.create_subprocess_exec）",
    "ctypes": _NATIVE, "_ctypes": _NATIVE, "cffi": _NATIVE, "winreg": "レジストリを変更できるため",
    "_winreg": "レジストリを変更できるため", "_winapi": _NATIVE, "msvcrt": _NATIVE, "mmap": _NATIVE,
    "win32api": _NATIVE, "win32con": _NATIVE, "win32gui": _NATIVE, "win32process": _NATIVE,
    "win32crypt": "保存されたパスワードを復号できるため", "win32clipboard": _NATIVE, "pywintypes": _NATIVE,
    "pickle": _DYN, "_pickle": _DYN, "marshal": _DYN, "shelve": _DYN, "dill": _DYN, "importlib": _DYN,
    "imp": _DYN, "runpy": _DYN, "code": _DYN, "codeop": _DYN, "zipimport": _DYN, "pkgutil": _DYN,
    "builtins": _DYN, "inspect": "アプリの内部の変数を読み書きできるため", "gc": "アプリの内部の変数を読み書きできるため",
    "socket": "通信の仕組みを直接使えるため（通信は urllib.request を使ってください）",
    "socketserver": "外からの接続を受け付けられるため", "http.server": "外からの接続を受け付けられるため",
    "xmlrpc": "外からの接続を受け付けられるため", "ftplib": "ファイルを外に送れるため",
    "smtplib": "メールを送れるため", "telnetlib": "外部のサーバーを操作できるため", "paramiko": "外部のサーバーを操作できるため",
    "keyboard": _INPUT, "pynput": _INPUT, "pyautogui": _INPUT, "mouse": _INPUT,
    "core": _INTERNAL, "cloud": _INTERNAL, "e2ee": _INTERNAL, "earo": _INTERNAL, "app": _INTERNAL, "dnd": _INTERNAL,
    "updater": _INTERNAL, "overlay": _INTERNAL, "dashboard": _INTERNAL, "discord_rpc": _INTERNAL,
    "monitor": _INTERNAL, "app_icon": _INTERNAL,
}
# ---- 使えない関数（名前 → 理由） ----
BLOCK_CALLS = {
    "eval": "文字から組み立てたコードを実行できるため", "exec": "文字から組み立てたコードを実行できるため",
    "compile": "文字から組み立てたコードを実行できるため", "__import__": "名前を組み立ててモジュールを読み込めるため",
    "globals": "アプリの内部の変数を読み書きできるため", "breakpoint": "アプリを止めてしまうため",
    "os.system": _EXEC, "os.popen": _EXEC, "os.startfile": "ファイルやプログラムを開けるため（ページを開くなら webbrowser）",
    "os.kill": "ほかのプログラムを終了できるため", "os.remove": "ファイルを削除できるため", "os.unlink": "ファイルを削除できるため",
    "os.rmdir": "フォルダを削除できるため", "os.removedirs": "フォルダを削除できるため", "os.fork": _EXEC,
    "os.chmod": "ファイルの権限を変えられるため", "os.chown": "ファイルの権限を変えられるため",
    "os.add_dll_directory": _NATIVE, "shutil.rmtree": "フォルダごと削除できるため", "shutil.chown": "ファイルの権限を変えられるため",
    "sys.settrace": "アプリの動きを書き換えられるため", "sys.setprofile": "アプリの動きを書き換えられるため",
    "sys._getframe": "アプリの内部の変数を読み書きできるため", "sys.addaudithook": "アプリの動きを書き換えられるため",
    "tkinter.Tk": "ウィンドウは api.root を親にして作ってください（Tk を2つ作るとアプリが不安定になります）",
}
BLOCK_CALL_PREFIXES = {"os.exec": _EXEC, "os.spawn": _EXEC, "os.posix_spawn": _EXEC}
BLOCK_SYS_ATTRS = {"modules", "meta_path", "path_hooks", "path_importer_cache", "settrace", "setprofile",
                   "_getframe", "addaudithook", "stdin"}
# どんなオブジェクトでも、この名前の属性は使えない
BLOCK_ATTRS = {
    "unlink": "ファイルを削除できるため", "rmdir": "フォルダを削除できるため", "rmtree": "フォルダごと削除できるため",
    "__globals__": "アプリの内部の変数を読み書きできるため", "__code__": "関数の中身を書き換えられるため",
    "__builtins__": "組み込みの関数を差し替えられるため", "__subclasses__": "制限を回避できるため",
    "__bases__": "制限を回避できるため", "__mro__": "制限を回避できるため", "__dict__": "非公開の値を読み書きできるため",
    "__loader__": "モジュールの読み込みを操作できるため", "__spec__": "モジュールの読み込みを操作できるため",
    "f_globals": "アプリの内部の変数を読み書きできるため", "f_locals": "アプリの内部の変数を読み書きできるため",
    "f_back": "アプリの内部の変数を読み書きできるため", "gi_frame": "アプリの内部の変数を読み書きできるため",
    "tb_frame": "アプリの内部の変数を読み書きできるため", "cloud": _INTERNAL,
    "app": "公開する MOD では WorkMonitor 本体（api.app）は使えません。api の機能を使ってください",
}
SAFE_DUNDER = {"__name__", "__doc__", "__file__", "__init__", "__class__", "__version__", "__all__", "__main__",
               "__enter__", "__exit__", "__len__", "__iter__", "__next__", "__str__", "__repr__", "__eq__", "__hash__"}
# Earo の api の非公開の名前（文字列で指定して触るのも防ぐ）
EARO_PRIVATE = {"_loader", "_mod", "_handlers", "_panels", "_actions", "_timers", "_dead", "_chains", "_register",
                "_cleanup", "_call"}
# 文字列にこれが含まれていたら不合格（パスワード・トークン・鍵などを盗む MOD によくある書き方）
SENSITIVE_STRINGS = [
    (re.compile(r"session\.bin", re.I), "WorkMonitor のログイン情報のファイル"),
    (re.compile(r"leveldb", re.I), "ブラウザや Discord の保存データ（トークンなど）"),
    (re.compile(r"login data", re.I), "ブラウザに保存されたパスワード"),
    (re.compile(r"\bcookies\b", re.I), "ブラウザの Cookie"),
    (re.compile(r"local state", re.I), "ブラウザの暗号鍵"),
    (re.compile(r"wallet", re.I), "暗号資産のウォレット"),
    (re.compile(r"(^|[\\/])\.ssh([\\/]|$)|id_rsa|id_ed25519", re.I), "SSH の鍵"),
    (re.compile(r"discord(canary|ptb)?[\\/]+local storage", re.I), "Discord のトークン"),
    (re.compile(r"\btelegram desktop\b|tdata", re.I), "Telegram のログイン情報"),
    (re.compile(r"mod_data[\\/]", re.I), "ほかの MOD の保存データ"),
]
WM_LOGS = re.compile(r"workmonitor.*logs|logs.*\.csv", re.I)
HIDDEN_CHARS = re.compile("[​-‏‪-‮⁦-⁩﻿]")
NETWORK_MODULES = {"urllib", "urllib.request", "http", "http.client", "requests", "aiohttp", "websocket", "ssl"}

PERMISSIONS = {
    "network": "インターネットに接続します",
    "browser": "ブラウザでページを開きます",
    "file_write": "ファイルを書き込みます",
    "file_read": "ファイルを読み込みます",
    "wm_logs": "WorkMonitor の作業記録を読みます",
    "thread": "裏で処理を動かします",
    "panel": "メイン画面に表示を追加します",
    "overlay": "オーバーレイの表示を変えます",
    "discord": "Discord の表示を変えます",
    "notify": "通知を出します",
    "sound": "音を鳴らします",
    "dialog": "ウィンドウを開きます",
}


class Review:
    def __init__(self):
        self.findings = []
        self.permissions = set()

    def block(self, message, file="", line=0):
        self.findings.append({"level": "block", "file": file, "line": line, "message": message})

    def note(self, message, file="", line=0):
        self.findings.append({"level": "note", "file": file, "line": line, "message": message})

    @property
    def ok(self):
        return not any(f["level"] == "block" for f in self.findings)


# ===== ファイルの形式 =====
def unpack(file_name, data, review):
    """投稿されたファイルから MOD のファイルを取り出す → (種類 "py"/"pkg", {MOD 内のパス: 中身}) """
    mod_id, ext = os.path.splitext(file_name)
    if not MOD_ID.match(mod_id) or ext not in (".py", ".zip"):
        review.block("ファイル名は「英小文字・数字・_・- で2〜40文字」+「.py か .zip」にしてください。")
        return None, {}
    if len(data) > MAX_UPLOAD:
        review.block(f"ファイルが大きすぎます（{MAX_UPLOAD // 1024}KB まで）。")
        return None, {}
    if ext == ".py":
        return "py", {f"{mod_id}.py": data}
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        review.block("zip ファイルとして開けませんでした。")
        return None, {}
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES:
        review.block(f"zip の中のファイルが多すぎます（{MAX_FILES} 個まで）。")
        return None, {}
    files, total = {}, 0
    for info in infos:
        name = info.filename
        parts = name.split("/")
        if name.startswith("/") or "\\" in name or ":" in name or ".." in parts or any(p == "" for p in parts):
            review.block(f"zip の中に危険な場所を指すファイルがあります: {name!r}")
            return None, {}
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            review.block(f"zip の中にショートカット（シンボリックリンク）があります: {name}")
            return None, {}
        if "__pycache__" in parts or os.path.splitext(name)[1].lower() not in ALLOWED_EXT:
            review.block(f"入れられない種類のファイルです: {name}（使えるのは {', '.join(sorted(ALLOWED_EXT))}）")
            continue
        if info.file_size > MAX_FILE:
            review.block(f"大きすぎるファイルがあります: {name}")
            return None, {}
        total += info.file_size
        if total > MAX_TOTAL:
            review.block(f"zip を展開すると大きすぎます（{MAX_TOTAL // 1024 // 1024}MB まで）。")
            return None, {}
        with z.open(info) as f:
            content = f.read(MAX_FILE + 1)
        if len(content) > MAX_FILE:
            review.block(f"大きすぎるファイルがあります: {name}")
            return None, {}
        files[name] = content
    if not review.ok:
        return None, {}
    # 構成: 「mod_id/__init__.py ...」か「__init__.py ...」（直下）か「.py 1つ」
    if "__init__.py" in files:
        return "pkg", {f"{mod_id}/{k}": v for k, v in files.items()}
    tops = {k.split("/")[0] for k in files}
    if len(tops) == 1 and len(files) > 0:
        top = tops.pop()
        if f"{top}/__init__.py" in files:
            if top != mod_id:
                review.block(f"zip の中のフォルダ名（{top}）を、ファイル名と同じ「{mod_id}」にしてください。")
                return None, {}
            return "pkg", files
    pys = [k for k in files if k.endswith(".py")]
    if len(files) == 1 and len(pys) == 1 and "/" not in pys[0]:
        if pys[0] != f"{mod_id}.py":
            review.block(f"zip の中の .py ファイルの名前を「{mod_id}.py」にしてください。")
            return None, {}
        return "py", files
    review.block("zip の中に MOD が見つかりません。「MOD 名のフォルダ/__init__.py」か「.py ファイル1つ」にしてください。")
    return None, {}


# ===== MOD_INFO と setup =====
def check_entry(tree, path, review):
    info = None
    has_setup = False
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MOD_INFO" for t in node.targets):
            try:
                info = ast.literal_eval(node.value)
            except ValueError:
                review.block("MOD_INFO は計算や変数を使わず、文字と数字をそのまま書いてください。", path, node.lineno)
        if isinstance(node, ast.FunctionDef) and node.name == "setup":
            has_setup = True
    if not has_setup:
        review.block("setup(api) という関数がありません。", path)
    if not isinstance(info, dict):
        if info is None:
            review.block("MOD_INFO がありません（name・version・author・description を書いてください）。", path)
        return {}
    clean = {}
    for key, limit, required in (("name", 60, True), ("version", 20, True), ("author", 60, True),
                                 ("description", 300, True)):
        value = info.get(key)
        if not isinstance(value, str) or not value.strip():
            review.block(f"MOD_INFO の「{key}」を文字で書いてください。", path)
            continue
        value = " ".join(value.split())
        if len(value) > limit:
            review.block(f"MOD_INFO の「{key}」が長すぎます（{limit} 文字まで）。", path)
        if HIDDEN_CHARS.search(value):
            review.block(f"MOD_INFO の「{key}」に見えない文字が入っています。", path)
        clean[key] = value
    if "version" in clean and not VERSION.match(clean["version"]):
        review.block("MOD_INFO の version は「1.0.0」のような数字と点の形にしてください。", path)
    api = info.get("api", 1)
    if not isinstance(api, int) or api < 1 or api > API_VERSION:
        review.block(f"MOD_INFO の api は {API_VERSION} 以下の整数にしてください。", path)
    clean["api"] = api if isinstance(api, int) else 1
    return clean


# ===== 危険な書き方 =====
class Scanner(ast.NodeVisitor):
    def __init__(self, path, review):
        self.path = path
        self.r = review
        self.aliases = {}   # ローカルの名前 → モジュールのフルネーム

    def block(self, node, message):
        self.r.block(message, self.path, getattr(node, "lineno", 0))

    def _module(self, name, node):
        for cand in (name, name.split(".")[0]):
            if cand in BLOCK_MODULES:
                self.block(node, f"「{name}」は使えません（{BLOCK_MODULES[cand]}）。")
                return
        top = name.split(".")[0]
        if name in NETWORK_MODULES or top in NETWORK_MODULES:
            self.r.permissions.add("network")
        if top == "webbrowser":
            self.r.permissions.add("browser")
        if top == "threading" or name == "concurrent.futures":
            self.r.permissions.add("thread")
        if top == "winsound":
            self.r.permissions.add("sound")

    def visit_Import(self, node):
        for a in node.names:
            self._module(a.name, node)
            self.aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level:   # MOD の中のファイル（from . import x）
            return
        mod = node.module or ""
        self._module(mod, node)
        for a in node.names:
            if a.name == "*":
                self.block(node, "「from ... import *」は使えません（何を使っているか確かめられないため）。")
                continue
            full = f"{mod}.{a.name}"
            self._module(full, node)
            self.aliases[a.asname or a.name] = full
        self.generic_visit(node)

    def _resolve(self, node):
        """os.path.join のような名前をフルネームにする（分からなければ None）"""
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        base = self.aliases.get(node.id, node.id)
        return ".".join([base] + parts[::-1])

    def visit_Call(self, node):
        name = self._resolve(node.func)
        if name:
            reason = BLOCK_CALLS.get(name)
            if reason is None and name not in BLOCK_CALLS:
                reason = next((r for p, r in BLOCK_CALL_PREFIXES.items() if name.startswith(p)), None)
            if reason:
                self.block(node, f"「{name}」は使えません（{reason}）。")
            if name in ("getattr", "setattr", "delattr", "hasattr") and len(node.args) >= 2:
                arg = node.args[1]
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    self.block(node, f"「{name}」で属性の名前を組み立てて使うことはできません（制限を回避できるため）。")
                else:
                    self._attr_name(arg.value, node, base=None)
            if name == "vars" and node.args:
                self.block(node, "「vars(...)」は使えません（非公開の値を読み書きできるため）。")
            if name in ("open", "io.open", "codecs.open"):
                mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
                mode_s = mode.value if isinstance(mode, ast.Constant) and isinstance(mode.value, str) else ("r" if mode is None else "w")
                self.r.permissions.add("file_write" if set(mode_s) & set("wax+") else "file_read")
            if name.split(".")[-1] in ("write_text", "write_bytes", "makedirs", "mkdir", "copyfile", "copy", "copy2",
                                       "copytree", "move", "rename", "replace") and name.split(".")[0] in ("os", "shutil", "pathlib") \
                    or name.endswith((".write_text", ".write_bytes")):
                self.r.permissions.add("file_write")
            if name.endswith((".read_text", ".read_bytes")) or name in ("os.listdir", "os.scandir", "os.walk", "glob.glob"):
                self.r.permissions.add("file_read")
            last = name.split(".")[-1]
            if last == "add_panel":
                self.r.permissions.add("panel")
            elif last == "notify":
                self.r.permissions.add("notify")
            elif last in ("on", "filter") and node.args and isinstance(node.args[0], ast.Constant):
                kind = node.args[0].value
                if kind == "overlay_text":
                    self.r.permissions.add("overlay")
                elif kind == "discord_text":
                    self.r.permissions.add("discord")
            elif name.startswith(("tkinter.messagebox", "tkinter.filedialog", "tkinter.simpledialog", "tkinter.Toplevel")) \
                    or name in ("Toplevel", "tk.Toplevel"):
                self.r.permissions.add("dialog")
        self.generic_visit(node)

    def _attr_name(self, attr, node, base):
        if attr == "app" and base in ("self", "cls"):
            return   # 自分のクラスの self.app はよい
        if attr in BLOCK_ATTRS:
            self.block(node, f"「.{attr}」は使えません（{BLOCK_ATTRS[attr]}）。")
        elif attr.startswith("__") and attr.endswith("__") and attr not in SAFE_DUNDER:
            self.block(node, f"「.{attr}」は使えません（制限を回避できるため）。")
        elif attr.startswith("_") and not attr.startswith("__") and base not in ("self", "cls"):
            # 自分のクラスの self._x はよいが、api._loader のようなほかの物の非公開の値は触らない
            self.block(node, f"「.{attr}」は使えません（ほかの物の非公開の値は触れないでください）。")

    def visit_Attribute(self, node):
        base = node.value.id if isinstance(node.value, ast.Name) else None
        self._attr_name(node.attr, node, base)
        full = self._resolve(node)
        if full:
            if full.startswith("sys.") and full.split(".")[1] in BLOCK_SYS_ATTRS:
                self.block(node, f"「{full}」は使えません（アプリの動きを書き換えられるため）。")
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in ("__builtins__", "__loader__", "__spec__"):
            self.block(node, f"「{node.id}」は使えません（制限を回避できるため）。")
        self.generic_visit(node)

    def visit_Constant(self, node):
        v = node.value
        if isinstance(v, (str, bytes)) and len(v) > MAX_STRING:
            self.block(node, f"とても長い文字列があります（{MAX_STRING} 文字まで。隠されたプログラムやデータの可能性があるため）。")
        if isinstance(v, str):
            for pattern, what in SENSITIVE_STRINGS:
                if pattern.search(v):
                    self.block(node, f"{what}を読み取ろうとしている可能性があります（{v[:40]!r}）。")
            if WM_LOGS.search(v):
                self.r.permissions.add("wm_logs")
            if v in EARO_PRIVATE or (v in BLOCK_ATTRS and v.startswith(("_", "f_", "gi_", "tb_"))):
                self.block(node, f"「{v}」という文字列は使えません（非公開の値に触れる書き方のため）。")


def scan_source(path, data, review, entry):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        review.block("文字コードを UTF-8 にしてください。", path)
        return None
    if HIDDEN_CHARS.search(text):
        line = text[:HIDDEN_CHARS.search(text).start()].count("\n") + 1
        review.block("見えない文字（ゼロ幅文字・文字の向きを変える文字）が入っています。見た目と中身が違うコードを防ぐため使えません。",
                     path, line)
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_LINE:
            review.block(f"1行が長すぎます（{MAX_LINE} 文字まで。読めないように詰め込んだコードを防ぐため）。", path, i)
            break
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as e:
        review.block(f"Python の文法エラーがあります: {e.msg}", path, e.lineno or 0)
        return None
    Scanner(path, review).visit(tree)
    return check_entry(tree, path, review) if entry else None


# ===== bandit =====
def run_bandit(files, review):
    """bandit が入っていれば使う（重大で確実な指摘だけ不合格、ほかは参考として残す）"""
    if not shutil.which("bandit"):
        review.note("bandit が見つからなかったため、bandit での検査は行いませんでした。")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files.items():
            if name.endswith(".py"):
                dest = os.path.join(tmp, *name.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(content)
        res = subprocess.run(["bandit", "-r", tmp, "-f", "json", "-q", "--skip", "B101,B311,B324"],
                             capture_output=True, text=True, timeout=120)
        try:
            results = json.loads(res.stdout or "{}").get("results", [])
        except ValueError:
            review.note("bandit の結果を読めませんでした。")
            return
        for item in results:
            path = os.path.relpath(item["filename"], tmp).replace(os.sep, "/")
            msg = f"bandit {item['test_id']}: {item['issue_text']}"
            if item["issue_severity"] == "HIGH" and item["issue_confidence"] in ("HIGH", "MEDIUM"):
                review.block(msg, path, item.get("line_number", 0))
            elif item["issue_severity"] in ("HIGH", "MEDIUM"):
                review.note(msg, path, item.get("line_number", 0))


# ===== まとめ =====
def review_mod(file_name, data, bandit=True):
    """審査する → dict(ok, mod_id, kind, info, files, report)。files は公開する MOD のファイル"""
    r = Review()
    mod_id = os.path.splitext(file_name)[0]
    kind, files = unpack(file_name, data, r)
    info = {}
    if kind:
        entry = f"{mod_id}.py" if kind == "py" else f"{mod_id}/__init__.py"
        for name, content in sorted(files.items()):
            if name.endswith(".py"):
                result = scan_source(name, content, r, name == entry)
                if name == entry:
                    info = result or {}
            else:
                # テキストのファイルにも見えない文字や機密の場所が書かれていないか
                if name.endswith((".txt", ".md", ".json", ".csv")):
                    try:
                        text = content.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        r.block("文字コードを UTF-8 にしてください。", name)
                        continue
                    for pattern, what in SENSITIVE_STRINGS:
                        if pattern.search(text):
                            r.block(f"{what}を指す文字が含まれています。", name)
        if bandit and r.ok:
            run_bandit(files, r)
    report = {
        "ok": r.ok,
        "findings": r.findings[:50],
        "permissions": sorted(r.permissions),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return {"ok": r.ok, "mod_id": mod_id, "kind": kind, "info": info, "files": files, "report": report}


def version_key(v):
    return tuple(int(x) for x in v.split("."))


if __name__ == "__main__":
    # 手元で試す: python tools/mod_review.py my_mod.py
    for p in sys.argv[1:]:
        with open(p, "rb") as f:
            res = review_mod(os.path.basename(p), f.read())
        print(f"== {p}: {'合格' if res['ok'] else '不合格'}  {res['info']}")
        for x in res["report"]["findings"]:
            print(f"  [{x['level']}] {x['file']}:{x['line']} {x['message']}")
        print("  この MOD が行うこと:", ", ".join(PERMISSIONS[p] for p in res["report"]["permissions"]) or "なし")
