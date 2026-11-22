# -*- coding: utf-8 -*-
"""把几台服务器上抓回来的 songs.json 合并进本地（只取歌词相关字段）。

用法：python merge_parts.py part1.json part2.json ...
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
FIELDS = ("lyrics", "lrc", "album", "netease", "lyrics_from", "nosync")


def main():
    parts = sys.argv[1:]
    if not parts:
        raise SystemExit("用法：python merge_parts.py a.json b.json ...")
    songs = json.load(open(SONGS, encoding="utf-8"))
    by = {s["id"]: s for s in songs}
    changed = []
    for p in parts:
        if not os.path.exists(p):
            print("跳过不存在的", p)
            continue
        for s in json.load(open(p, encoding="utf-8")):
            if not str(s.get("lyrics_from", "")).startswith("netease"):
                continue
            cur = by.get(s["id"])
            if not cur:
                continue
            if cur.get("lyrics_from") == s.get("lyrics_from"):
                continue
            for f in FIELDS:
                if f in s:
                    cur[f] = s[f]
            changed.append(cur["title"])
    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("合并了 %d 首：%s" % (len(changed), "、".join(changed) or "（无变化）"))


if __name__ == "__main__":
    main()
