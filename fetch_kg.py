# -*- coding: utf-8 -*-
"""读全民K歌全部作品（需要登录 Cookie），取每首歌最晚一次翻唱的日期。

Cookie 来源：CDP 里登录后导出的 _kg_cookies.json（本地，不入库）。

用法：python fetch_kg.py
"""
import json
import os
import re
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
COOKIES = os.path.join(ROOT, "_kg_cookies.json")
UID = "609999822d2d3e8d31"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://static-play.kg.qq.com/",
    "X-Requested-With": "XMLHttpRequest",
}
API = "https://node.kg.qq.com/fcgi-bin/kg_ugc_get_homepage"


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"[～~·・\s\-_/、，,。.！!？?'\"“”\[\]]", "", s)
    return s


def session():
    s = requests.Session()
    s.headers.update(H)
    if os.path.exists(COOKIES):
        for c in json.load(open(COOKIES, encoding="utf-8")):
            s.cookies.set(c["name"], c["value"], domain=c.get("domain") or ".qq.com",
                          path=c.get("path") or "/")
    return s


def fetch_all(s):
    out, start, empty = [], 1, 0
    while start < 400:
        try:
            r = s.get(API, params={"type": "get_ugc", "start": start, "num": 10,
                                   "touin": "", "share_uid": UID,
                                   "outCharset": "utf-8", "format": "json"}, timeout=25)
            j = r.json()
        except Exception as e:  # noqa: BLE001
            print("  page %d err %s" % (start, e))
            time.sleep(3)
            empty += 1
            if empty > 3:
                break
            continue
        d = j.get("data") or {}
        lst = d.get("ugclist") or []
        seen = {w.get("time") for w in lst}
        if not lst:
            empty += 1
            if empty > 2:
                break
        else:
            empty = 0
            new = [w for w in lst if all(w.get("time") != x.get("time") or w.get("title") != x.get("title")
                                         for x in out)]
            out.extend(new)
            print("  page %3d: +%-2d  累计 %d / %s" % (start, len(new), len(out),
                                                     d.get("ugc_total_count")))
        start += 10
        time.sleep(0.8)
    return out


def main():
    s = session()
    works = fetch_all(s)
    print("作品 %d 条" % len(works))
    if not works:
        print("没拿到数据：先确认 _kg_cookies.json 是不是登录后导出的")
        return
    songs = json.load(open(SONGS, encoding="utf-8"))
    index = {}
    for w in works:
        k = norm(w.get("title"))
        if k:
            index.setdefault(k, []).append(w)

    hit, miss = 0, []
    for song in songs:
        k = norm(song["title"])
        cands = index.get(k) or []
        if not cands and len(k) >= 3:
            cands = [w for kk, ws in index.items()
                     if kk and (kk.startswith(k) or k.startswith(kk)) for w in ws]
        if not cands:
            miss.append(song["title"])
            continue
        cands.sort(key=lambda w: w.get("time") or 0, reverse=True)
        latest = cands[0]
        ts = int(latest.get("time") or 0)
        song["kg"] = {
            "date": time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else "",
            "ts": ts,
            "title": latest.get("title"),
            "versions": len(cands),
            "play": latest.get("play_count"),
        }
        hit += 1
        print("  %-26s ← %-26s %s（%d 个版本）" % (song["title"], latest.get("title"),
                                                  song["kg"]["date"], len(cands)))
    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n对上 %d/%d 首" % (hit, len(songs)))
    if miss:
        print("K歌那边没找到：")
        for m in miss:
            print("  -", m)




if __name__ == "__main__":
    main()

