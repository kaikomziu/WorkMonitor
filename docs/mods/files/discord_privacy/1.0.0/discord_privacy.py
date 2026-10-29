"""Discord のぼかし

Discord に出す文から、アプリ名をかくしてカテゴリだけにします。
"""

MOD_INFO = {
    "name": "Discord のぼかし",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "Discord のステータスに出るアプリ名をかくし、「開発の作業中」のようにカテゴリだけ出します。",
    "api": 1,
}


def setup(api):
    @api.filter("discord_text")
    def discord(text, info):
        name = info.get("name") or ""
        if name and name in text:
            text = text.replace(name, "ひみつ")
        cat = info.get("category")
        if cat and cat not in text:
            text = text.replace("作業中", f"{cat}の作業中")
        return text
