"""Discord Rich Presence 連携（外部ライブラリ不要）

Discord デスクトップアプリの名前付きパイプ（\\\\.\\pipe\\discord-ipc-N）に
直接つないで、プロフィールに「作業中 ◯:◯◯ 経過」を表示する。
"""

import json
import os
import struct
import time
import uuid

OP_HANDSHAKE = 0
OP_FRAME = 1


class DiscordPresence:
    RETRY_SEC = 30        # 接続失敗後に再接続を試す間隔
    MIN_UPDATE_SEC = 15   # Discord のレート制限（20秒に5回）対策

    def __init__(self, client_id):
        self.client_id = str(client_id)
        self.pipe = None
        self.last_try = 0.0
        self.last_sent = 0.0
        self.last_key = None
        self.status = "未接続"  # 画面表示用

    # ---- 低レベル通信 ----
    def _send(self, op, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.pipe.write(struct.pack("<II", op, len(data)) + data)
        self.pipe.flush()
        return self._recv()

    def _recv(self):
        header = self.pipe.read(8)
        if len(header) < 8:
            raise OSError("Discord との接続が切れました")
        _op, length = struct.unpack("<II", header)
        return json.loads(self.pipe.read(length).decode("utf-8"))

    def _connect(self):
        self.last_try = time.time()
        for i in range(10):
            try:
                self.pipe = open(rf"\\.\pipe\discord-ipc-{i}", "r+b", buffering=0)
                break
            except OSError:
                continue
        else:
            self.status = "Discord が起動していません"
            return False
        try:
            resp = self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
            if resp.get("evt") != "READY":
                # client_id の間違いなど
                self.status = f"接続エラー: {resp.get('message', resp)}"
                self._disconnect()
                return False
            self.status = "接続中"
            return True
        except (OSError, ValueError):
            self.status = "接続エラー"
            self._disconnect()
            return False

    def _disconnect(self):
        if self.pipe:
            try:
                self.pipe.close()
            except OSError:
                pass
        self.pipe = None
        self.last_key = None

    def _set_activity(self, activity):
        self._send(OP_FRAME, {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": str(uuid.uuid4()),
        })

    # ---- 監視ループから呼ぶ ----
    def update(self, working, today_sec, details="作業中"):
        """状態が変わったときだけ Discord に送る（details は作業中に出す文言）"""
        now = time.time()
        if self.pipe is None:
            if now - self.last_try < self.RETRY_SEC or not self._connect():
                return

        # 作業中は「今日の合計」から逆算した開始時刻を渡すと、Discord 側で秒数が進み続ける
        key = (working, details if working else "")
        if key == self.last_key or now - self.last_sent < self.MIN_UPDATE_SEC:
            return

        if working:
            activity = {
                "details": details,
                "state": "今日の作業時間",
                "timestamps": {"start": int((now - today_sec) * 1000)},
            }
        else:
            h, m = int(today_sec // 3600), int(today_sec % 3600 // 60)
            activity = {"details": "休憩中", "state": f"今日の作業 {h}時間{m:02d}分"}

        try:
            self._set_activity(activity)
            self.last_key = key
            self.last_sent = now
        except (OSError, ValueError):
            self.status = "接続が切れました（再接続待ち）"
            self._disconnect()

    def close(self):
        if self.pipe:
            try:
                self._set_activity(None)
            except (OSError, ValueError):
                pass
        self._disconnect()
