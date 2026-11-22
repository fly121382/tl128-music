# -*- coding: utf-8 -*-
"""清理 songs.json 里的歌词：去掉连续重复行、空行、广告尾巴。"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(ROOT, "data", "songs.json")

BAD = re.compile(r"(本歌曲|酷狗|网易云|未经许可|不得翻唱|翻录|QQ音乐|歌词校对|LRC|请欣赏)")


def key(s):
    return re.sub(r"[\s:：、,，.。!！?？\-—]", "", s)


def clean(lines):
    out, seen = [], set()
    for line in lines or []:
        s = (line or "").strip()
        if not s:
            continue
        if BAD.search(s) and len(s) < 40:
            continue
        k = key(s)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(s)
    # 去掉首尾多余的分隔行
    while out and key(out[0]) in ("", "-", "—"):
        out.pop(0)
    while out and key(out[-1]) in ("", "-", "—"):
        out.pop()
    return out


def main():
    songs = json.load(open(P, encoding="utf-8"))
    n = 0
    for s in songs:
        before = len(s.get("lyrics") or [])
        s["lyrics"] = clean(s.get("lyrics"))
        if before != len(s["lyrics"]):
            n += 1
    json.dump(songs, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("cleaned", n, "songs; lyrics present:", sum(1 for s in songs if s["lyrics"]),
          "; avg lines:", round(sum(len(s["lyrics"]) for s in songs) / max(1, len(songs)), 1))


if __name__ == "__main__":
    main()
