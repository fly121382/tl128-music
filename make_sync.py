# -*- coding: utf-8 -*-
"""用 songs.json 里已存的 LRC（网易云 / lrclib 带时间轴的那份）补齐同步歌词。

规则：时间轴末行与录音时长差 ≤20 秒才用；>8 秒的标 approx（可能在整体偏移，交给 ± 微调）。

用法：python make_sync.py [--force]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SYNC = os.path.join(ROOT, "data", "sync")
TS = re.compile(r"^\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$")
META = re.compile(r"^\[(ti|ar|al|by|offset|kana|language):", re.I)


def parse(lrc):
    pairs = []
    for line in (lrc or "").split("\n"):
        line = line.strip()
        if not line or META.match(line):
            continue
        m = TS.match(line)
        if not m:
            continue
        mm, ss, frac, body = m.group(1), m.group(2), m.group(3) or "0", m.group(4).strip()
        if not body:
            continue
        t = int(mm) * 60 + int(ss) + int(frac.ljust(3, "0")) / 1000.0
        pairs.append((round(t, 2), body))
    pairs.sort(key=lambda x: x[0])
    ded = []
    for t, txt in pairs:
        if ded and ded[-1][1] == txt:
            continue
        ded.append((t, txt))
    return ded


def main():
    force = "--force" in sys.argv
    os.makedirs(SYNC, exist_ok=True)
    songs = json.load(open(SONGS, encoding="utf-8"))
    added, skipped, approx = [], [], []
    for s in songs:
        path = os.path.join(SYNC, s["id"] + ".timing.json")
        if os.path.exists(path) and not force:
            continue
        if s.get("nosync"):
            skipped.append((s["id"], "标记为不同步"))
            continue
        pairs = parse(s.get("lrc"))
        if len(pairs) < 8:
            skipped.append((s["id"], "时间轴太短"))
            continue
        # 只要拿到时间轴就挂上：长度差得多就标 approx，由用户在播放器里微调或关掉同步
        gap = abs(pairs[-1][0] - s["dur"])
        if gap > 20:
            gap = 99
        s["lyrics"] = [t for _x, t in pairs]
        json.dump({"id": s["id"], "title": s["title"], "dur": s["dur"], "approx": gap > 8,
                   "lines": [{"t": t, "s": txt} for t, txt in pairs]},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        (approx if gap > 8 else added).append((s["id"], round(gap, 1), len(pairs)))
    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("新增同步（可信）：%d" % len(added))
    for x in added:
        print("  %-24s 差%-5s %d 行" % x)
    print("新增同步（近似，需微调）：%d" % len(approx))
    for x in approx:
        print("  %-24s 差%-5s %d 行" % x)
    print("跳过：%d" % len(skipped))
    for x in skipped:
        print("  %-24s %s" % x)
    n = sum(1 for s in songs if os.path.exists(os.path.join(SYNC, s["id"] + ".timing.json")))
    print("\n共 %d/%d 首有同步歌词" % (n, len(songs)))


if __name__ == "__main__":
    main()


