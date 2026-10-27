"""GitHub Releases で新しいバージョンが出ているか確認する"""

import json
import re
import ssl
import urllib.request

import core

API_URL = f"https://api.github.com/repos/{core.GITHUB_REPO}/releases/latest"
# TLS 1.2 以上・証明書の検証あり
TLS_CONTEXT = ssl.create_default_context()
TLS_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2


def parse_version(text):
    """'v1.2.3' → (1, 2, 3)"""
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3])


def check_latest(timeout=10):
    """新しいバージョンがあれば (バージョン, リリースページの URL)、無ければ None

    通信に失敗したときも None（オフラインでもアプリは普通に動くように）。
    """
    req = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{core.APP_NAME}/{core.APP_VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=TLS_CONTEXT) as res:
            data = json.load(res)
    except (OSError, ValueError):
        return None
    tag = data.get("tag_name", "")
    if not tag or parse_version(tag) <= parse_version(core.APP_VERSION):
        return None
    return tag.lstrip("v"), data.get("html_url", f"https://github.com/{core.GITHUB_REPO}/releases/latest")
