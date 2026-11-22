# -*- coding: utf-8 -*-
"""补齐 fetch_meta.py 漏掉的封面/歌词（慢速重试，多种查询词）。

用法：python fill_gaps.py [--all]
"""
import json
import os
import sys
import time

import requests

import fetch_meta as F

SONGS = F.SONGS


def try_one(rec):
    title, artist = rec["title"], rec.get("artist", "")
    queries = ["%s %s" % (title, artist), title, "%s 原唱" % title]
    best, score, cands = None, -1, []
    for q in queries:
        try:
            cands = F.search(q)
        except Exception as e:  # noqa: BLE001
            print("  search fail: %s" % e)
            cands = []
        time.sleep(1.5)
        if cands:
            best, score = F.pick(cands, title, artist)
            if best and score >= 3:
                break
    if not best or score < 3:
        return False, score
    sid = best["id"]
    rec["netease"] = sid
    rec["album"] = rec.get("album") or (best.get("album") or {}).get("name", "")
    rec["match"] = round(score, 1)
    if not rec.get("cover"):
        try:
            d = F.detail(sid)
            time.sleep(1.0)
            pic = ((d or {}).get("album") or {}).get("picUrl", "")
            if pic:
                img = requests.get(pic + "?param=600y600", headers=F.H, timeout=30)
                if img.ok and len(img.content) > 5000:
                    cp = os.path.join(F.COVERS, rec["id"] + ".jpg")
                    open(cp, "wb").write(img.content)
                    rec["cover"] = "assets/covers/%s.jpg" % rec["id"]
        except Exception as e:  # noqa: BLE001
            print("  cover fail: %s" % e)
    if not rec.get("lyrics"):
        try:
            lrc, tlrc = F.lyric(sid)
            time.sleep(1.0)
            rec["lrc"] = lrc
            rec["lyrics"] = F.plain(lrc)
            if tlrc:
                rec["tlyric"] = F.plain(tlrc)
        except Exception as e:  # noqa: BLE001
            print("  lyric fail: %s" % e)
    return True, score


def main():
    all_mode = "--all" in sys.argv
    songs = json.load(open(SONGS, encoding="utf-8"))
    todo = [s for s in songs
            if all_mode or not s.get("cover") or not s.get("lyrics")]
    print("todo %d" % len(todo))
    for i, rec in enumerate(todo, 1):
        ok, score = try_one(rec)
        print("[%d/%d] %-8s cover=%d lyrics=%d  %s" %
              (i, len(todo), round(score, 1) if ok else "miss",
               bool(rec.get("cover")), len(rec.get("lyrics") or []), rec["id"]))
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.5)
    print("\ncover=%d lyrics=%d / %d" %
          (sum(1 for s in songs if s.get("cover")),
           sum(1 for s in songs if s.get("lyrics")), len(songs)))
    miss = [s["title"] for s in songs if not s.get("cover") or not s.get("lyrics")]
    if miss:
        print("still missing:")
        for t in miss:
            print(" -", t)


if __name__ == "__main__":
    main()
