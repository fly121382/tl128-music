# -*- coding: utf-8 -*-
"""给还缺歌词的歌再抓一轮：lrclib（清掉括号里的说明）→ 网易云（慢速）。"""
import json
import os
import re
import sys
import time

import requests

import fetch_meta as F

SONGS = F.SONGS
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def clean_artist(a):
    a = re.sub(r"[（(][^）)]*[）)]", "", a or "")
    a = re.split(r"[、,，/]", a)[0]
    return a.strip()


def lrclib(title, artist):
    for params in (
        {"track_name": title, "artist_name": artist},
        {"q": "%s %s" % (title, artist)},
        {"q": title},
    ):
        try:
            r = requests.get("https://lrclib.net/api/search", params=params, headers=UA, timeout=25)
            arr = r.json()
        except Exception as e:  # noqa: BLE001
            print("  lrclib err", e)
            continue
        if not isinstance(arr, list) or not arr:
            time.sleep(1)
            continue
        arr.sort(key=lambda x: 0 if F.norm(x.get("trackName")) == F.norm(title) else 1)
        for it in arr[:6]:
            if F.norm(it.get("trackName")) != F.norm(title):
                continue
            body = (it.get("plainLyrics") or "").strip()
            if len(body.split("\n")) < 5:
                continue
            return body, (it.get("syncedLyrics") or ""), (it.get("albumName") or "")
        time.sleep(1)
    return None


def netease(title, artist):
    try:
        r = requests.get("https://music.163.com/api/search/get/web",
                         params={"s": "%s %s" % (title, artist), "type": 1, "limit": 6},
                         headers={**UA, "Referer": "https://music.163.com/"}, timeout=25)
        j = r.json()
        if j.get("code") != 200:
            print("  netease code", j.get("code"))
            return None
        cands = ((j.get("result") or {}).get("songs") or [])
    except Exception as e:  # noqa: BLE001
        print("  netease err", e)
        return None
    best, score = F.pick(cands, title, artist)
    if not best or score < 3:
        return None
    time.sleep(2)
    try:
        lrc, _ = F.lyric(best["id"])
    except Exception as e:  # noqa: BLE001
        print("  lyric err", e)
        return None
    lines = F.plain(lrc)
    if len(lines) < 5:
        return None
    return "\n".join(lines), lrc, (best.get("album") or {}).get("name", "")


def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    todo = [s for s in songs if not s.get("lyrics")]
    print("todo", len(todo))
    for i, s in enumerate(todo, 1):
        title, artist = s["title"], clean_artist(s.get("artist"))
        got = lrclib(title, artist)
        src = "lrclib"
        if not got:
            time.sleep(3)
            got = netease(title, artist)
            src = "netease"
        if not got:
            print("[%d/%d] MISS %s" % (i, len(todo), s["id"]))
            time.sleep(2)
            continue
        body, synced, album = got
        s["lyrics"] = [l.strip() for l in body.split("\n") if l.strip()]
        s["lrc"] = synced or s.get("lrc") or ""
        s["lyrics_from"] = src
        if album and not s.get("album"):
            s["album"] = album
        print("[%d/%d] %s ok (%d lines, %s)" % (i, len(todo), s["id"], len(s["lyrics"]), src))
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(2)
    print("lyrics now:", sum(1 for s in songs if s.get("lyrics")), "/", len(songs))
    for s in songs:
        if not s.get("lyrics"):
            print("  still:", s["title"])


if __name__ == "__main__":
    main()
