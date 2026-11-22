# -*- coding: utf-8 -*-
"""用本地音乐库里的 .lrc 补歌词 / 补时间轴。

库：E:\\音乐\\神之曲1（2800 个 .lrc，带 [mm:ss.xx] 时间轴）
规则：
  - 歌名强匹配 + 原唱匹配才算命中；
  - 时间轴末行与我的录音时长差 ≤ 20 秒 → 视为同一版伴奏，直接当同步歌词用；
  - 差太多 → 只取文本，不取时间轴（避免歌词乱跳）。

用法：python match_lrc.py [--apply]
"""
import json
import os
import re
import sys

import fetch_meta as F

LIB = r"E:\音乐\神之曲1"
SYNC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sync")
TS = re.compile(r"^\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$")
META = re.compile(r"^\[(ti|ar|al|by|offset):", re.I)


def read_lrc(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "big5"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse(text):
    pairs, meta = [], {}
    for line in text.split("\n"):
        line = line.rstrip("\r")
        m = META.match(line)
        if m:
            k = line[1:line.index(":")]
            meta[k.lower()] = line[line.index(":") + 1:-1].strip()
            continue
        m = TS.match(line.strip())
        if not m:
            continue
        mm, ss, frac, body = m.group(1), m.group(2), m.group(3) or "0", m.group(4)
        t = int(mm) * 60 + int(ss) + int(frac.ljust(3, "0")) / 1000.0
        body = body.strip()
        if not body or body.startswith("//"):
            continue
        pairs.append((round(t, 2), body))
    pairs.sort(key=lambda x: x[0])
    return pairs, meta


def score(stem, title, artist, dmax, dur):
    s, parts = 0, [p.strip() for p in re.split(r"\s+-\s+|\s*-\s*", stem) if p.strip()]
    nt = F.norm(title)
    if any(F.norm(p) == nt for p in parts):
        s += 6
    elif nt and nt in F.norm(stem):
        s += 3
    else:
        return -99
    for a in re.split(r"[、,，/]", artist or ""):
        a = F.norm(re.sub(r"[（(][^）)]*[）)]", "", a or ""))
        if a and a in F.norm(stem):
            s += 4
            break
    gap = abs((dmax or 0) - dur)
    if gap <= 8:
        s += 3
    elif gap <= 20:
        s += 1
    elif gap > 60:
        s -= 3
    return s


def main():
    apply_ = "--apply" in sys.argv
    os.makedirs(SYNC, exist_ok=True)
    files = []
    for root, _dirs, names in os.walk(LIB):
        for n in names:
            if n.lower().endswith(".lrc"):
                files.append(os.path.join(root, n))
    print("库内 lrc：%d" % len(files))

    songs = json.load(open(F.SONGS, encoding="utf-8"))
    cache = {}
    hit, text_only, miss = [], [], []
    for s in songs:
        title, artist = s["title"], s.get("artist", "")
        nt = F.norm(title)
        best, bs = None, -99
        for path in files:
            stem = os.path.splitext(os.path.basename(path))[0]
            if nt not in F.norm(stem):
                continue
            try:
                pairs, meta = cache[path] if path in cache else parse(read_lrc(path))
            except Exception:  # noqa: BLE001
                continue
            cache[path] = (pairs, meta)
            if not pairs:
                continue
            dmax = pairs[-1][0]
            sc = score(stem, title, artist, dmax, s["dur"])
            if sc > bs:
                best, bs = (path, pairs), sc
        if not best or bs < 6:
            miss.append((s["id"], bs))
            continue
        path, pairs = best
        dmax = pairs[-1][0]
        aligned = abs(dmax - s["dur"]) <= 20
        # 去掉相邻重复行（保留带时间的首个）
        ded = []
        for t, txt in pairs:
            if ded and ded[-1][1] == txt:
                continue
            if txt in ("纯音乐，请欣赏", "暂无歌词"):
                continue
            ded.append((t, txt))
        pairs = ded
        lines = [t for _ts, t in pairs]
        if len(lines) < 5:
            miss.append((s["id"], bs))
            continue
        if apply_:
            if aligned:
                s["lyrics"] = lines
                s["lyrics_from"] = "lrc:" + os.path.basename(path)
                json.dump({"id": s["id"], "title": title, "dur": s["dur"],
                           "lines": [{"t": t, "s": txt} for t, txt in pairs]},
                          open(os.path.join(SYNC, s["id"] + ".timing.json"), "w",
                               encoding="utf-8"), ensure_ascii=False)
            elif not s.get("lyrics"):
                s["lyrics"] = lines
                s["lyrics_from"] = "lrc:" + os.path.basename(path)
        (hit if aligned else text_only).append(
            (s["id"], round(bs, 1), round(dmax - s["dur"], 1), os.path.basename(path)))

    print("\n可用同步（时长差 ≤20s）：%d" % len(hit))
    for x in hit:
        print("  SYNC %-28s score=%-4s gap=%-6s %s" % x)
    print("\n只取歌词（时长不符）：%d" % len(text_only))
    for x in text_only:
        print("  TEXT %-28s score=%-4s gap=%-6s %s" % x)
    print("\n没匹配到：%d" % len(miss))
    for i, sc in miss:
        print("  MISS %s (best %s)" % (i, sc))
    if apply_:
        json.dump(songs, open(F.SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n已写回 songs.json / data/sync/")


if __name__ == "__main__":
    main()
