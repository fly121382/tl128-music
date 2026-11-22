# -*- coding: utf-8 -*-
"""按 星标候选.md 里的勾选结果写回 songs.json（star 字段）。

用法：python apply_stars.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SRC = os.path.join(ROOT, "星标候选.md")


def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    if not os.path.exists(SRC):
        raise SystemExit("找不到 星标候选.md，先跑 make_star_list.py")
    text = open(SRC, encoding="utf-8").read()
    picked = set()
    for line in text.split("\n"):
        m = re.match(r"^\|\s*\[([xX✔✓√])\s*\]\s*\|\s*(\d+)\s*\|", line)
        if m:
            picked.add(int(m.group(2)))
    n = 0
    for i, s in enumerate(songs, 1):
        s["star"] = i in picked
        n += 1 if s["star"] else 0
    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("星标 %d 首：" % n)
    for i, s in enumerate(songs, 1):
        if s["star"]:
            print("  %2d. %s — %s" % (i, s["title"], s.get("artist")))
    if not n:
        print("  （还没勾）")


if __name__ == "__main__":
    main()

