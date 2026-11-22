# -*- coding: utf-8 -*-
"""慢速补抓：只处理还没拿到网易云歌词的歌，请求间隔拉长到 12 秒，避开 405。

用法：python refetch_slow.py
"""
import json
import os
import re
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
COVERS = os.path.join(ROOT, "data", "covers")
GAP = 12
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


def get(url, params, tries=4, wait=45):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=25)
            j = r.json()
            if j.get("code") == 200:
                return j
            print("   code %s (wait %ds)" % (j.get("code"), wait), flush=True)
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
    return out


def plain(lines):
    out = []
    for _t, s in lines:
        if BAD.search(s) and len(s) < 40:
            continue
        if out and out[-1] == s:
            continue
        out.append(s)
    return out


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
    todo = [s for s in songs if not str(s.get("lyrics_from", "")).startswith("netease")]
    print("待补 %d 首" % len(todo), flush=True)
    for n, s in enumerate(todo, 1):
        title, artist, dur = s["title"], s.get("artist") or "", s["dur"]
        sid = s.get("netease") if s.get("netease") else 0
        if not sid:
            j = get("https://music.163.com/api/search/get/web",
                    {"s": "%s %s" % (title, artist), "type": 1, "limit": 10})
            time.sleep(GAP)
            cands = ((j or {}).get("result") or {}).get("songs") or []
            best = pick(cands, title, artist, dur)
            if not best:
                print("[%02d/%d] MISS  %s" % (n, len(todo), s["title"]), flush=True)
                continue
            sid = best["id"]
        ly = get("https://music.163.com/api/song/lyric", {"id": sid, "lv": 1, "kv": 1, "tv": -1})
        time.sleep(GAP)
        lrc = ((ly or {}).get("lrc") or {}).get("lyric", "")
        lines = parse(lrc)
        if len(lines) < 4:
            print("[%02d/%d] NOLRC %s" % (n, len(todo), s["title"]), flush=True)
            continue
        s["netease"] = sid
        s["lrc"] = lrc
        s["lyrics"] = plain(lines)
        s["lyrics_from"] = "netease:%s" % sid
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[%02d/%d] OK    %-24s %d 行 末行%.1fs" % (n, len(todo), s["title"],
                                                          len(s["lyrics"]), lines[-1][0]), flush=True)
    print("完成", flush=True)


if __name__ == "__main__":
    main()
