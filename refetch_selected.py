# -*- coding: utf-8 -*-
"""只补指定几首歌的歌词 + 时间轴（慢速，避免 405）。

用法：python refetch_selected.py 歌名1 歌名2 ...
      python refetch_selected.py --missing      # 自动挑「没有时间轴」且不是 nosync 的
"""
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SYNC = os.path.join(ROOT, "data", "sync")
COVERS = os.path.join(ROOT, "data", "covers")
GAP = int(os.environ.get('TL_GAP', '15'))
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://music.163.com/",
}
BAD = re.compile(r"(本歌曲|酷狗|网易云音乐|未经许可|不得翻唱|翻录|QQ音乐|歌词校对|请欣赏)")


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"[～~·・\s\-_/、，,。.！!？?'\"“”\[\]]", "", s)
    return s


def tokens(a):
    out = []
    for t in re.split(r"[、,，/]", a or ""):
        t = re.sub(r"[（(][^）)]*[）)]", "", t).strip()
        if t:
            out.append(norm(t))
    return [x for x in out if x]


def get(url, params, tries=4, wait=40):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=25)
            j = r.json()
            if j.get("code") == 200:
                return j
            print("   code %s wait %ds" % (j.get("code"), wait), flush=True)
        except Exception as e:  # noqa: BLE001
            print("   err %s" % e, flush=True)
        time.sleep(wait)
    return None


def parse(lrc):
    out = []
    for line in (lrc or "").split("\n"):
        m = re.match(r"^\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$", line.strip())
        if not m:
            continue
        body = m.group(4).strip()
        if not body:
            continue
        t = int(m.group(1)) * 60 + int(m.group(2)) + int((m.group(3) or "0").ljust(3, "0")) / 1000.0
        out.append((round(t, 2), body))
    out.sort(key=lambda x: x[0])
    ded = []
    for t, s in out:
        if ded and ded[-1][1] == s:
            continue
        ded.append((t, s))
    return ded


def pick(cands, title, artist, dur):
    nt, tk = norm(title), tokens(artist)
    best, bs = None, -1
    for i, c in enumerate(cands):
        if norm(c.get("name")) != nt:
            continue
        names = [norm(a.get("name")) for a in (c.get("artists") or [])]
        if not any(t in n for t in tk for n in names):
            continue
        score = 10 - i * 0.3
        d = (c.get("duration") or 0) / 1000.0
        gap = abs(d - dur) if d else 999
        score += 6 if gap <= 5 else 3 if gap <= 15 else 1 if gap <= 40 else -4
        if score > bs:
            best, bs = c, score
    return best


def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--missing" in sys.argv or not args:
        want = [s for s in songs
                if not s.get("nosync")
                and not os.path.exists(os.path.join(SYNC, s["id"] + ".timing.json"))]
    else:
        want = [s for s in songs if s["title"] in args]
    print("处理 %d 首: %s" % (len(want), "、".join(s["title"] for s in want)), flush=True)

    for n, s in enumerate(want, 1):
        title, artist, dur = s["title"], s.get("artist") or "", s["dur"]
        j = get("https://music.163.com/api/search/get/web",
                {"s": "%s %s" % (title, artist), "type": 1, "limit": 10})
        time.sleep(GAP)
        cands = ((j or {}).get("result") or {}).get("songs") or []
        best = pick(cands, title, artist, dur)
        if not best:
            print("[%d/%d] MISS %s" % (n, len(want), title), flush=True)
            continue
        ly = get("https://music.163.com/api/song/lyric",
                 {"id": best["id"], "lv": 1, "kv": 1, "tv": -1})
        time.sleep(GAP)
        lines = parse(((ly or {}).get("lrc") or {}).get("lyric", ""))
        if len(lines) < 8:
            print("[%d/%d] NOLRC %s" % (n, len(want), title), flush=True)
            continue
        gap = abs(lines[-1][0] - dur)
        s["netease"] = best["id"]
        s["lrc"] = ((ly or {}).get("lrc") or {}).get("lyric", "")
        s["lyrics"] = [t for _x, t in lines]
        s["lyrics_from"] = "netease:%s" % best["id"]
        if (best.get("album") or {}).get("name"):
            s["album"] = best["album"]["name"]
        ok = gap <= 20 or lines[-1][0] > dur
        print("[%d/%d] %s %-22s %d 行 末行%.0fs/%.0fs %s" % (
            n, len(want), "OK  " if ok else "NOTE", title, len(lines),
            lines[-1][0], dur, "（可同步）" if ok else "（长度差太多，先只给歌词）"), flush=True)
        if ok:
            json.dump({"id": s["id"], "title": title, "dur": dur, "approx": gap > 8,
                       "lines": [{"t": t, "s": txt} for t, txt in lines]},
                      open(os.path.join(SYNC, s["id"] + ".timing.json"), "w",
                           encoding="utf-8"), ensure_ascii=False)
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("完成", flush=True)


if __name__ == "__main__":
    main()

