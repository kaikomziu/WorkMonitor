"""Earo — WorkMonitor の MOD ローダー

MOD は Python のファイル（.py）か、__init__.py の入ったフォルダ。
%APPDATA%\\WorkMonitor\\mods に置いてオンにすると読み込まれ、setup(api) が呼ばれる。
MOD の作り方は mods/modreadme.txt を参照（起動時に mods フォルダにもコピーする）。

MOD の処理で例外が起きてもアプリは落とさない。エラーが続いた MOD は自動で止める。
"""

import ast
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
import zipfile
from collections import deque, namedtuple
from tkinter import ttk

import core

# exe 版でも MOD から使えるように、よく使う標準モジュールを同梱させる（PyInstaller は import したものだけを入れるため）
import calendar, csv, datetime, hashlib, math, random, statistics, string, textwrap, urllib.parse, urllib.request, uuid, winsound  # noqa: E401,F401,E402
from tkinter import colorchooser, filedialog, simpledialog  # noqa: F401,E402

LOADER_NAME = "Earo"
LOADER_VERSION = "1.0.0"
API_VERSION = 1                 # MOD_INFO["api"] がこれより大きい MOD は読み込まない
MODS_DIR = os.path.join(core.DATA_DIR, "mods")
MOD_DATA_DIR = os.path.join(core.DATA_DIR, "mod_data")
# 同梱の modreadme.txt と作例（exe 版は展開先の一時フォルダ、Python 版はこのファイルの隣）
RESOURCE_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "mods")
README_NAME = "modreadme.txt"
EXAMPLES_NAME = "examples"
MAX_ERRORS = 10                 # これだけエラーが続いたら、その MOD を止める
EVENTS = ("tick", "state_change", "app_change", "goal_reached", "day_change", "quit")
FILTERS = ("overlay_text", "discord_text")
STATUS_TEXT = {"off": "オフ", "on": "✓ 動作中", "error": "✗ エラー", "stopped": "✗ 停止（エラーが続いた）",
               "waiting": "待機（MOD 読み込みがオフ）"}


class InstallError(Exception):
    pass


# ドロップされたものを調べた結果。kind: "py" / "dir" / "zip"。member: zip の中の MOD の場所
Plan = namedtuple("Plan", "path mod_id kind member exists")


def safe_mode():
    """--no-mods 付きで起動したら MOD を一切読み込まない（MOD のせいで起動できないとき用）"""
    return "--no-mods" in sys.argv


def read_info(mod_id, entry):
    """MOD_INFO をプログラムを実行せずに読む（オフの MOD も一覧に名前や説明を出すため）"""
    info = {"name": mod_id, "version": "", "author": "", "description": "", "api": 1}
    try:
        with open(entry, "rb") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MOD_INFO" for t in node.targets):
                value = ast.literal_eval(node.value)
                if isinstance(value, dict):
                    for k in info:
                        if k in value:
                            info[k] = value[k] if k == "api" else str(value[k])
    except (OSError, SyntaxError, ValueError):
        pass
    return info


def valid_id(mod_id):
    return bool(re.fullmatch(r"[^\W_][\w\-]*", mod_id)) and mod_id.lower() != EXAMPLES_NAME


class Mod:
    def __init__(self, mod_id, path, is_pkg):
        self.id = mod_id
        self.path = path
        self.is_pkg = is_pkg
        self.entry = os.path.join(path, "__init__.py") if is_pkg else path
        self.info = read_info(mod_id, self.entry)
        self.module = None
        self.api = None
        self.status = "off"
        self.error = ""
        self.errors = 0
        self.logs = deque(maxlen=300)

    @property
    def loaded(self):
        return self.api is not None

    @property
    def name(self):
        return self.info["name"] or self.id

    def log(self, text):
        for line in str(text).rstrip().splitlines() or [""]:
            self.logs.append(f"{time.strftime('%H:%M:%S')}  {line}")


class ModAPI:
    """MOD の setup(api) に渡すもの。MOD ができることはこれにまとまっている（使い方は modreadme.txt）"""

    def __init__(self, loader, mod):
        self._loader = loader
        self._mod = mod
        self._handlers = {e: [] for e in EVENTS + FILTERS}
        self._panels = []
        self._actions = []
        self._timers = set()
        self._dead = False
        self.id = mod.id
        self.mod_dir = mod.path if mod.is_pkg else MODS_DIR
        self.data_path = os.path.join(MOD_DATA_DIR, f"{mod.id}.json")
        self.data = {}
        try:
            with open(self.data_path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            pass

    # ---- 情報 ----
    @property
    def app(self):
        """WorkMonitor 本体（App）。上級者向け。中身はバージョンアップで変わることがある"""
        return self._loader.app

    @property
    def root(self):
        return self._loader.app.root

    @property
    def version(self):
        return core.APP_VERSION

    @property
    def dark(self):
        return self._loader.app.dark

    @property
    def colors(self):
        app = self._loader.app
        return {"text": "#e8eaf0" if app.dark else "#1d2330", "sub": app.sub_color, "bg": app.bg,
                "accent": "#4f6bed", "green": "#22a06b", "orange": "#e2a03f", "red": "#d9534f"}

    def status(self):
        return self._loader.status()

    def config(self):
        """設定のコピー（変えても本体には反映されない）"""
        return json.loads(json.dumps(self._loader.app.config))

    # ---- イベント・フィルター ----
    def on(self, event, func=None):
        """イベントに関数を登録する。@api.on("tick") のようにデコレーターとしても使える"""
        if event not in EVENTS:
            raise ValueError(f"知らないイベントです: {event}（使えるのは {', '.join(EVENTS)}）")
        return self._register(event, func)

    def filter(self, name, func=None):
        """表示する文字を書き換える関数を登録する。@api.filter("overlay_text") のようにも使える"""
        if name not in FILTERS:
            raise ValueError(f"知らないフィルターです: {name}（使えるのは {', '.join(FILTERS)}）")
        return self._register(name, func)

    def _register(self, name, func):
        if func is None:
            return lambda f: self._register(name, f)
        self._handlers[name].append(func)
        if self._mod.loaded:
            self._loader._rebuild_chains()
        return func

    # ---- 画面 ----
    def add_panel(self, build, title=None):
        """メイン画面に枠を足す。build(frame) は画面を作り直すたびに呼ばれる"""
        self._panels.append((title, build))
        if self._mod.loaded:
            self._loader.render_panels()

    def refresh_panels(self):
        self._loader.render_panels()

    def add_action(self, text, func):
        """設定 → Mods でこの MOD を選んだときに出るボタンを足す"""
        self._actions.append((text, func))
        self._loader._changed()

    def notify(self, text, title=None):
        self._loader.app._notify(str(text), title or self._mod.name)

    def after(self, ms, func, *args):
        """ms ミリ秒後に func を画面のスレッドで呼ぶ。MOD を止めると自動で取り消す"""
        if self._dead:
            return None
        holder = []

        def run():
            self._timers.discard(holder[0])
            if not self._dead:
                self._loader._call(self._mod, func, *args)
        holder.append(self.root.after(int(ms), run))
        self._timers.add(holder[0])
        return holder[0]

    def cancel(self, timer_id):
        if timer_id in self._timers:
            self._timers.discard(timer_id)
            self.root.after_cancel(timer_id)

    def call_soon(self, func, *args):
        """別スレッドから、画面のスレッドで func を呼んでもらう（Tk の部品は画面のスレッドでしか触れない）"""
        if not self._dead:
            self._loader.app.events.put(lambda: self._dead or self._loader._call(self._mod, func, *args))

    # ---- 保存・ログ ----
    def save_data(self):
        os.makedirs(MOD_DATA_DIR, exist_ok=True)
        tmp = self.data_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.data_path)

    def log(self, *values):
        self._mod.log(" ".join(str(v) for v in values))
        self._loader._changed()

    def _cleanup(self):
        self._dead = True
        for t in list(self._timers):
            try:
                self.root.after_cancel(t)
            except Exception:
                pass
        self._timers.clear()


class Earo:
    def __init__(self, app):
        self.app = app
        self.mods = {}
        self.safe_mode = safe_mode()
        self.on_change = None          # Mods タブが開いている間、一覧を更新する関数
        self._chains = {}              # イベント名 → ((mod, 関数), ...)。別スレッドからも読むので丸ごと差し替える
        self._prev = None
        self._last_tick = 0.0
        self._change_pending = False
        self._gui_thread = threading.get_ident()

    # ---- 設定 ----
    @property
    def settings(self):
        return self.app.config.setdefault("mods", {"enabled": True, "active": {}})

    @property
    def enabled(self):
        return self.settings.get("enabled", True) and not self.safe_mode

    def _save(self):
        core.save_config(self.app.config)

    # ---- 準備・一覧 ----
    def prepare(self):
        """mods フォルダを作り、最新の modreadme.txt と作例を置く"""
        os.makedirs(MODS_DIR, exist_ok=True)
        src = os.path.join(RESOURCE_DIR, README_NAME)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(MODS_DIR, README_NAME))
        examples = os.path.join(RESOURCE_DIR, EXAMPLES_NAME)
        if os.path.isdir(examples):
            shutil.copytree(examples, os.path.join(MODS_DIR, EXAMPLES_NAME), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))

    def scan(self):
        found = {}
        try:
            names = sorted(os.listdir(MODS_DIR), key=str.lower)
        except OSError:
            names = []
        for name in names:
            full = os.path.join(MODS_DIR, name)
            if name.startswith(("_", ".")):
                continue
            if os.path.isdir(full):
                if os.path.isfile(os.path.join(full, "__init__.py")) and valid_id(name):
                    found[name] = (full, True)
            elif name.lower().endswith(".py") and valid_id(name[:-3]):
                found.setdefault(name[:-3], (full, False))
        for mod_id in list(self.mods):
            mod = self.mods[mod_id]
            if found.get(mod_id) != (mod.path, mod.is_pkg):
                self.unload(mod)
                del self.mods[mod_id]
        for mod_id, (path, is_pkg) in found.items():
            if mod_id not in self.mods:
                self.mods[mod_id] = Mod(mod_id, path, is_pkg)
            elif not self.mods[mod_id].loaded:
                self.mods[mod_id].info = read_info(mod_id, self.mods[mod_id].entry)
        self._changed()

    def load_all(self):
        try:
            self.prepare()
        except OSError:
            pass
        self.scan()
        if self.enabled:
            for mod in list(self.mods.values()):
                if self.is_active(mod.id):
                    self.load(mod)
        else:
            for mod in self.mods.values():
                mod.status = "waiting" if self.is_active(mod.id) else "off"

    def is_active(self, mod_id):
        return bool(self.settings.setdefault("active", {}).get(mod_id))

    def loaded_mods(self):
        return [m for m in self.mods.values() if m.loaded]

    # ---- 読み込み・停止 ----
    def _module_name(self, mod):
        return "earo_mod_" + re.sub(r"\W", "_", mod.id)

    def _forget_module(self, mod):
        name = self._module_name(mod)
        for k in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[k]

    def load(self, mod):
        if mod.loaded:
            return True
        mod.info = read_info(mod.id, mod.entry)
        mod.errors, mod.error = 0, ""
        need = mod.info.get("api", 1)
        if isinstance(need, int) and need > API_VERSION:
            mod.status = "error"
            mod.error = f"新しい Earo（API {need}）が必要です。アプリを更新してください。"
            mod.log(mod.error)
            self._changed()
            return False
        api = ModAPI(self, mod)
        try:
            self._forget_module(mod)
            spec = importlib.util.spec_from_file_location(
                self._module_name(mod), mod.entry, submodule_search_locations=[mod.path] if mod.is_pkg else None)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            setup = getattr(module, "setup", None)
            if not callable(setup):
                raise InstallError("setup(api) という関数がありません")
            mod.module, mod.api = module, api
            setup(api)
        except (Exception, SystemExit) as e:
            api._cleanup()
            mod.module = mod.api = None
            self._forget_module(mod)
            mod.status = "error"
            mod.error = f"{type(e).__name__}: {e}" if not isinstance(e, InstallError) else str(e)
            mod.log("読み込みに失敗しました\n" + traceback.format_exc())
            self._changed()
            return False
        mod.status = "on"
        mod.log(f"読み込みました（{mod.name} {mod.info['version']}）".replace(" ）", "）"))
        self._rebuild_chains()
        self.render_panels()
        self._changed()
        return True

    def unload(self, mod, status="off"):
        if mod.api:
            teardown = getattr(mod.module, "teardown", None)
            if callable(teardown):
                self._call(mod, teardown, mod.api)
            mod.api._cleanup()
            mod.module = mod.api = None
            self._forget_module(mod)
            mod.log("止めました")
            self._rebuild_chains()
            self.render_panels()
        mod.status = status
        self._changed()

    def reload(self, mod):
        self.unload(mod)
        mod.info = read_info(mod.id, mod.entry)
        if self.enabled and self.is_active(mod.id):
            self.load(mod)

    def reload_all(self):
        for mod in self.loaded_mods():
            self.unload(mod)
        self.scan()
        self.load_all()

    def set_active(self, mod, active):
        self.settings.setdefault("active", {})[mod.id] = bool(active)
        self._save()
        if not active:
            self.unload(mod)
        elif self.enabled:
            self.load(mod)
        else:
            mod.status = "waiting"
            self._changed()

    def set_enabled(self, enabled):
        self.settings["enabled"] = bool(enabled)
        self._save()
        if self.enabled:
            for mod in self.mods.values():
                if self.is_active(mod.id):
                    self.load(mod)
        else:
            for mod in self.mods.values():
                self.unload(mod, "waiting" if self.is_active(mod.id) else "off")

    def shutdown(self):
        self.emit("quit")
        for mod in self.loaded_mods():
            self.unload(mod)

    # ---- 追加・削除 ----
    def inspect(self, path):
        """ドロップされたものを調べる。MOD として入れられなければ InstallError"""
        path = os.path.abspath(path.rstrip("\\/"))
        name = os.path.basename(path)
        member = None
        if os.path.isdir(path):
            if not os.path.isfile(os.path.join(path, "__init__.py")):
                raise InstallError("フォルダの MOD には __init__.py が必要です")
            mod_id, kind = name, "dir"
        elif name.lower().endswith(".py"):
            mod_id, kind = name[:-3], "py"
        elif name.lower().endswith(".zip"):
            mod_id, member = self._zip_plan(path)
            kind = "zip"
        else:
            raise InstallError("MOD として入れられるのは .py ファイル・フォルダ・.zip です")
        if not valid_id(mod_id):
            raise InstallError(f"「{mod_id}」は MOD の名前に使えません（英数字・日本語・_・- で、_ 以外から始まる名前にしてください）")
        exists = os.path.exists(os.path.join(MODS_DIR, mod_id)) or os.path.exists(os.path.join(MODS_DIR, mod_id + ".py"))
        return Plan(path, mod_id, kind, member, exists)

    @staticmethod
    def _zip_plan(path):
        """zip の中から MOD を探す → (MOD の名前, 中の場所)。場所は "" か "フォルダ/"（パッケージ）、".py ファイル名"（単体）"""
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
        except (OSError, zipfile.BadZipFile):
            raise InstallError("zip ファイルを開けませんでした")
        for n in names:
            parts = n.replace("\\", "/").split("/")
            if n.startswith(("/", "\\")) or ".." in parts or ":" in n:
                raise InstallError("zip の中に危険な場所を指すファイルがあります")
        stem = os.path.basename(path)[:-4]
        if "__init__.py" in names:
            return stem, ""
        tops = {n.split("/")[0] for n in names}
        if len(tops) == 1:
            top = tops.pop()
            if f"{top}/__init__.py" in names:
                return top, top + "/"
        if len(names) == 1 and names[0].lower().endswith(".py") and "/" not in names[0]:
            return names[0][:-3], names[0]
        raise InstallError("zip の中に MOD（__init__.py のあるフォルダか、.py ファイル1つ）が見つかりません")

    def _remove_files(self, mod_id):
        folder = os.path.join(MODS_DIR, mod_id)
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        if os.path.isfile(folder + ".py"):
            os.remove(folder + ".py")

    def install(self, plan):
        """MOD を mods フォルダにコピーしてオンにする。読み込みに失敗しても入れたままにする（一覧でエラーを見られる）"""
        os.makedirs(MODS_DIR, exist_ok=True)
        dest_dir = os.path.join(MODS_DIR, plan.mod_id)
        dest = dest_dir if plan.kind == "dir" or (plan.kind == "zip" and not plan.member.endswith(".py")) \
            else dest_dir + ".py"
        if os.path.abspath(plan.path) != os.path.abspath(dest):   # mods フォルダの中のものならコピー不要
            if plan.mod_id in self.mods:
                self.unload(self.mods[plan.mod_id])
            self._remove_files(plan.mod_id)
            if plan.kind == "py":
                shutil.copyfile(plan.path, dest)
            elif plan.kind == "dir":
                shutil.copytree(plan.path, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                with zipfile.ZipFile(plan.path) as z:
                    if plan.member.endswith(".py"):
                        with z.open(plan.member) as s, open(dest, "wb") as d:
                            shutil.copyfileobj(s, d)
                    else:
                        for info in z.infolist():
                            if info.is_dir() or not info.filename.startswith(plan.member):
                                continue
                            target = os.path.join(dest, *info.filename[len(plan.member):].split("/"))
                            os.makedirs(os.path.dirname(target), exist_ok=True)
                            with z.open(info) as s, open(target, "wb") as d:
                                shutil.copyfileobj(s, d)
        self.scan()
        mod = self.mods.get(plan.mod_id)
        if mod is None:
            raise InstallError("コピーしたあと MOD が見つかりませんでした")
        mod.log("追加しました")
        self.set_active(mod, True)
        return mod

    def remove(self, mod):
        self.unload(mod)
        self._remove_files(mod.id)
        self.settings.setdefault("active", {}).pop(mod.id, None)
        self._save()
        self.mods.pop(mod.id, None)
        self._changed()

    # ---- 呼び出し ----
    def _call(self, mod, func, *args, default=None):
        """MOD の関数を呼ぶ。例外はログに残してアプリは止めない"""
        try:
            return func(*args)
        except (Exception, SystemExit):
            mod.errors += 1
            mod.error = traceback.format_exc().strip().splitlines()[-1]
            mod.log(traceback.format_exc())
            if mod.errors >= MAX_ERRORS and mod.loaded:
                mod.log(f"エラーが {MAX_ERRORS} 回起きたので止めました（直してから「再読み込み」してください）")
                self.app.events.put(lambda: mod.loaded and self.unload(mod, "stopped"))
            self._changed()
            return default

    def _rebuild_chains(self):
        chains = {name: [] for name in EVENTS + FILTERS}
        for mod in self.loaded_mods():
            for name, funcs in mod.api._handlers.items():
                chains[name].extend((mod, f) for f in funcs)
        self._chains = {k: tuple(v) for k, v in chains.items()}

    def emit(self, event, *args):
        for mod, func in self._chains.get(event, ()):
            self._call(mod, func, *args)

    def apply_filter(self, name, value, *args):
        for mod, func in self._chains.get(name, ()):
            result = self._call(mod, func, value, *args, default=value)
            if isinstance(result, str):
                value = result
        return value

    def discord_filter(self, text, info):
        """監視スレッドから呼ばれる（Monitor.discord_filter）"""
        return self.apply_filter("discord_text", text, dict(info))

    def status(self):
        app = self.app
        m = app.monitor
        cfg = app.config
        info = core.app_info(cfg, m.app) if m.app else {"name": "", "category": "", "count": False}
        goal = cfg.get("daily_goal_min", 0)
        return {
            "state": m.state,
            "app": m.app,
            "app_name": info["name"],
            "category": info["category"],
            "counted": bool(info["count"]),
            "today_sec": int(m.today_sec),
            "today_by_app": {k: int(v) for k, v in m.today_by_name().items()},
            "goal_min": goal,
            "goal_done": goal > 0 and m.today_sec >= goal * 60,
        }

    def tick(self):
        """メイン画面の定期更新から呼ばれる。1秒ごとにイベントを出す"""
        if not self._chains or not any(self._chains.get(e) for e in ("tick", "state_change", "app_change")):
            self._prev = None
            return
        now = time.monotonic()
        if now - self._last_tick < 0.9:   # 画面の更新は 0.5 秒ごとなので、だいたい 1 秒ごとになる
            return
        self._last_tick = now
        st = self.status()
        prev, self._prev = self._prev, st
        if prev:
            if prev["state"] != st["state"]:
                self.emit("state_change", prev["state"], st["state"], st)
            if prev["app"] != st["app"]:
                self.emit("app_change", prev["app"], st["app"], st)
        self.emit("tick", st)

    # ---- 画面 ----
    def render_panels(self):
        frame = getattr(self.app, "f_mods", None)
        if frame is None or not frame.winfo_exists():
            return
        for w in frame.winfo_children():
            w.destroy()
        for mod in self.loaded_mods():
            for title, build in mod.api._panels:
                ttk.Separator(frame).pack(fill="x", pady=12)
                if title:
                    ttk.Label(frame, text=title, foreground=self.app.sub_color).pack(anchor="w")
                body = ttk.Frame(frame)
                body.pack(fill="x", pady=(6 if title else 0, 0))
                self._call(mod, build, body)

    def _changed(self):
        """Mods タブの表示を更新する（別スレッドからでもよいように、画面のスレッドでまとめて行う）"""
        if self.on_change is None or self._change_pending:
            return
        self._change_pending = True

        def run():
            self._change_pending = False
            if self.on_change:
                self.on_change()
        self.app.events.put(run)
