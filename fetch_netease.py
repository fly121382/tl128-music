# -*- coding: utf-8 -*-
"""抓网易云主页的歌单（自建 / 收藏），存成 data/netease.json 给「网易云」页用。

用法：python fetch_netease.py
"""
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "data", "netease.json")
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://music.163.com/",
}
SHORT = "https://163cn.tv/blDNtFDC"


def jget(s, url, params=None, tries=3):
    for i in range(tries):
        try:
            r = s.get(url, params=params, timeout=25)
            j = r.json()
            if j.get("code") == 200:
                return j
            print("  code %s, retry %d" % (j.get("code"), i + 1))
        except Exception as e:  # noqa: BLE001
            print("  err %s, retry %d" % (e, i + 1))
        time.sleep(4 + i * 3)
    return None


def main():
    s = requests.Session()
    s.headers.update(UA)
    r = s.get(SHORT, timeout=25, allow_redirects=True)
    m = re.search(r"id=(\d+)", r.url)
    if not m:
        sys.exit("拿不到 uid：%s" % r.url)
    uid = m.group(1)
    print("uid", uid)

    raw = []
    offset = 0
    while True:
        j = jget(s, "https://music.163.com/api/user/playlist",
                 {"uid": uid, "offset": offset, "limit": 100})
        if not j:
            break
        batch = j.get("playlist") or []
        raw.extend(batch)
        more = j.get("more")
        if not more or not batch:
            break
        offset += len(batch)
        time.sleep(1.2)

    base = raw[0] if raw else {}
    nickname = (base.get("creator") or {}).get("nickname", "")
    print("歌单数", len(raw), "昵称", nickname)

    out = []
    for i, p in enumerate(raw, 1):
        pid = p["id"]
        rec = {
            "id": pid, "name": p.get("name"), "cover": p.get("coverImgUrl"),
            "count": p.get("trackCount"), "play": p.get("playCount"),
            "own": (p.get("creator") or {}).get("userId") == int(uid) and not p.get("subscribed"),
            "sub": bool(p.get("subscribed")),
            "desc": p.get("description") or "",
            "updated": p.get("updateTime"),
            "tracks": [],
            "url": "https://music.163.com/playlist?id=%d" % pid,
        }
        d = jget(s, "https://music.163.com/api/v6/playlist/detail", {"id": pid, "n": 1000, "s": 0})
        time.sleep(0.9)
        if d and d.get("playlist"):
            pl = d["playlist"]
            rec["desc"] = rec["desc"] or (pl.get("description") or "")
            rec["tracks"] = [{"n": t.get("name"),
                              "a": ", ".join(x.get("name", "") for x in (t.get("ar") or []))}
                             for t in (pl.get("tracks") or [])[:8]]
        out.append(rec)
        print("[%3d/%d] %-28s %5s 首  %s" %
              (i, len(raw), (rec["name"] or "")[:28], rec["count"],
               "自建" if rec["own"] else "收藏"))

    json.dump({"updated": time.strftime("%Y-%m-%d %H:%M"), "uid": uid,
               "nickname": nickname, "short": SHORT, "playlists": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    own = sum(1 for x in out if x["own"])
    print("\n自建 %d / 收藏 %d → %s" % (own, len(out) - own, OUT))


if __name__ == "__main__":
    main()

