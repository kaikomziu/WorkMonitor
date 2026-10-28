"""ウィンドウへのファイルのドラッグ＆ドロップを受け取る（Windows の WM_DROPFILES を使う）

Tk だけではエクスプローラーからのドロップを受け取れないため、ウィンドウの処理（WNDPROC）を
差し替えて WM_DROPFILES だけを横取りする。それ以外のメッセージは元の処理に渡す。
差し替えた処理の中で Tk を呼ぶと Python ごと落ちるため、ドロップされたものはためておき、
画面の定期更新から poll() で受け渡す。
"""

import ctypes
import ctypes.wintypes as wt
import traceback
from collections import deque

WM_DROPFILES = 0x0233
WM_NCDESTROY = 0x0082
GWLP_WNDPROC = -4

user32 = ctypes.WinDLL("user32")
shell32 = ctypes.WinDLL("shell32")
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = (wt.HWND,)
user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.SetWindowLongPtrW.argtypes = (wt.HWND, ctypes.c_int, ctypes.c_void_p)
user32.CallWindowProcW.restype = LRESULT
user32.CallWindowProcW.argtypes = (ctypes.c_void_p, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
shell32.DragAcceptFiles.argtypes = (wt.HWND, wt.BOOL)
shell32.DragQueryFileW.restype = wt.UINT
shell32.DragQueryFileW.argtypes = (wt.HANDLE, wt.UINT, wt.LPWSTR, wt.UINT)
shell32.DragFinish.argtypes = (wt.HANDLE,)

_hooks = {}         # hwnd → [元の処理, 差し替えた処理, 受け取る関数]
_retired = []       # 閉じたウィンドウの処理（呼び出し中に解放されないよう参照を残す）
_pending = deque()  # (受け取る関数, パスのリスト)


def _paths(hdrop):
    try:
        count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        paths = []
        for i in range(count):
            size = shell32.DragQueryFileW(hdrop, i, None, 0) + 1
            buf = ctypes.create_unicode_buffer(size)
            shell32.DragQueryFileW(hdrop, i, buf, size)
            paths.append(buf.value)
        return paths
    finally:
        shell32.DragFinish(hdrop)


def enable(window, callback):
    """window（Tk / Toplevel）にファイルがドロップされたら callback(パスのリスト) を呼ぶ"""
    window.update_idletasks()
    hwnd = user32.GetParent(window.winfo_id())   # Tk の枠のウィンドウ
    if not hwnd:
        return False
    if hwnd in _hooks:
        _hooks[hwnd][2] = callback
        return True

    def proc(h, msg, wparam, lparam):
        hook = _hooks.get(hwnd)
        if hook is None:
            return 0
        if msg == WM_DROPFILES:
            try:
                _pending.append((hook[2], _paths(wparam)))   # Tk はここでは呼ばない
            except Exception:
                pass
            return 0
        if msg == WM_NCDESTROY:
            _retired.append(_hooks.pop(hwnd))
        return user32.CallWindowProcW(hook[0], h, msg, wparam, lparam)

    new_proc = WNDPROC(proc)
    old_proc = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(new_proc, ctypes.c_void_p))
    if not old_proc:
        return False
    _hooks[hwnd] = [old_proc, new_proc, callback]
    shell32.DragAcceptFiles(hwnd, True)
    return True


def poll():
    """ためておいたドロップを受け取る関数に渡す（画面のスレッドで定期的に呼ぶ）"""
    while _pending:
        callback, paths = _pending.popleft()
        if paths:
            try:
                callback(paths)
            except Exception:   # 定期更新を止めないように
                traceback.print_exc()
