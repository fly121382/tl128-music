# -*- coding: utf-8 -*-
"""给 songs.json 补封面与歌词：iTunes / Kugou 取图，lrclib 取词。

用法：python collect.py [--covers] [--lyrics]
不带参数 = 全部补齐。
"""
import json
import os
import re
import sys
import time
import urllib.parse

import requests

import fetch_meta as F

SONGS = F.SONGS
COVERS = F.COVERS
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}


def jget(url, params=None, timeout=25):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- covers
def itunes_cover(title, artist):
    j = jget("https://itunes.apple.com/search",
             {"term": "%s %s" % (title, artist), "entity": "song", "limit": 12})
    best, bs = None, -1.0
    for i, it in enumerate(j.get("results", [])):
        score = 0.0
        if F.norm(it.get("trackName")) == F.norm(title):
            score += 5
        elif F.norm(title) and F.norm(title) in F.norm(it.get("trackName")):
            score += 2
        if F.norm(artist) and F.norm(artist) in F.norm(it.get("artistName")):
            score += 4
        if re.search(r"\b(live|remix|karaoke|instrumental)\b", (it.get("trackName") or ""), re.I):
            score -= 2
        score -= i * 0.05
        if score > bs:
            best, bs = it, score
    if not best or bs < 4:
        return None
    url = (best.get("artworkUrl100") or "").replace("100x100bb", "600x600bb")
    return url or None


def kugou_cover(title, artist):
    j = jget("http://mobilecdn.kugou.com/api/v3/search/song",
             {"keyword": "%s %s" % (title, artist), "page": 1, "pagesize": 5})
    info = ((j.get("data") or {}).get("info") or [])
    for it in info:
        if F.norm(title) not in F.norm(it.get("songname", "")):
            continue
        aid = it.get("album_id")
        if not aid or aid == "0":
            continue
        try:
            a = jget("http://mobilecdn.kugou.com/api/v3/album/info", {"albumid": aid})
            img = ((a.get("data") or {}).get("imgurl") or "")
            if img:
                return img.replace("{size}", "480")
        except Exception:  # noqa: BLE001
            continue
    return None


def grab_cover(rec):
    for fn in (itunes_cover, kugou_cover):
        try:
            url = fn(rec["title"], rec.get("artist", ""))
        except Exception as e:  # noqa: BLE001
            print("  %s fail: %s" % (fn.__name__, e))
            url = None
        if not url:
            continue
        try:
            img = requests.get(url, headers=UA, timeout=30)
            if img.ok and len(img.content) > 4000:
                cp = os.path.join(COVERS, rec["id"] + ".jpg")
                open(cp, "wb").write(img.content)
                rec["cover"] = "assets/covers/%s.jpg" % rec["id"]
                rec["cover_from"] = fn.__name__
                return True
        except Exception as e:  # noqa: BLE001
            print("  download fail: %s" % e)
        time.sleep(0.3)
    return False


# ---------------------------------------------------------------- lyrics
def lrclib_lyrics(title, artist, dur):
    j = jget("https://lrclib.net/api/search",
             {"track_name": title, "artist_name": artist})
    cands = j if isinstance(j, list) else []
    if not cands:
        j = jget("https://lrclib.net/api/search", {"q": "%s %s" % (title, artist)})
        cands = j if isinstance(j, list) else []
    best, bs = None, -1.0
    for it in cands:
        score = 0.0
        if F.norm(it.get("trackName")) == F.norm(title):
            score += 5
        elif F.norm(title) and F.norm(title) in F.norm(it.get("trackName")):
            score += 2
        if F.norm(artist) and F.norm(artist) in F.norm(it.get("artistName")):
            score += 4
        d = it.get("duration") or 0
        if d and abs(d - dur) < 6:
            score += 3
        elif d and abs(d - dur) < 20:
            score += 1
        if it.get("instrumental"):
            score -= 5
        if score > bs:
            best, bs = it, score
    if not best or bs < 6:
        return None
    return best.get("plainLyrics") or "", best.get("syncedLyrics") or "", best.get("albumName") or ""


def grab_lyrics(rec):
    try:
        got = lrclib_lyrics(rec["title"], rec.get("artist", ""), rec["dur"])
    except Exception as e:  # noqa: BLE001
        print("  lrclib fail: %s" % e)
        return False
    if not got:
        return False
    plain, synced, album = got
    lines = [l.strip() for l in (plain or "").split("\n") if l.strip()]
    if len(lines) < 4:
        return False
    rec["lyrics"] = lines
    rec["lrc"] = synced or rec.get("lrc") or ""
    rec["lyrics_from"] = "lrclib"
    if album and not rec.get("album"):
        rec["album"] = album
    return True


def main():
    do_covers = "--lyrics" not in sys.argv
    do_lyrics = "--covers" not in sys.argv
    songs = json.load(open(SONGS, encoding="utf-8"))
    for i, rec in enumerate(songs, 1):
        changed = False
        if do_covers and not rec.get("cover"):
            changed |= grab_cover(rec)
            time.sleep(0.5)
        if do_lyrics and not rec.get("lyrics"):
            changed |= grab_lyrics(rec)
            time.sleep(0.5)
        if changed:
            json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[%02d/%d] cover=%d lyrics=%d  %s" %
              (i, len(songs), bool(rec.get("cover")), len(rec.get("lyrics") or []), rec["id"]))
    print("\ncover=%d lyrics=%d / %d" % (
        sum(1 for s in songs if s.get("cover")),
        sum(1 for s in songs if s.get("lyrics")), len(songs)))
    miss = [(s["title"], bool(s.get("cover")), bool(s.get("lyrics")))
            for s in songs if not s.get("cover") or not s.get("lyrics")]
    for t, c, l in miss:
        print("  MISS cover=%d lyrics=%d  %s" % (c, l, t))


if __name__ == "__main__":
    main()
