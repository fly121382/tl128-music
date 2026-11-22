# -*- coding: utf-8 -*-
"""纯标准库版：抓指定歌曲的网易云歌词（不需要 requests）。

用法：python3 fetch_srv.py 歌名1 歌名2 ... [--gap 60]
产物：data/songs.json（就地更新）+ data/sync/*.timing.json
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SYNC = os.path.join(ROOT, "data", "sync")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
HDR = {"User-Agent": UA, "Referer": "https://music.163.com/"}
BAD = re.compile(r"(本歌曲|酷狗|网易云音乐|未经许可|不得翻唱|翻录|QQ音乐|歌词校对|请欣赏)")
TS = re.compile(r"^\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$")


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


def jget(url, params, gap, tries=4):
    q = urllib.parse.urlencode(params)
    full = url + "?" + q
    for i in range(tries):
        try:
            req = urllib.request.Request(full, headers=HDR)
            with urllib.request.urlopen(req, timeout=25) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
            if j.get("code") == 200:
                return j
            print("   code %s wait %ds" % (j.get("code"), gap), flush=True)
        except Exception as e:  # noqa: BLE001
            print("   err %s" % e, flush=True)
        time.sleep(gap)
    return None


def parse(lrc):
    out = []
    for line in (lrc or "").split("\n"):
        m = TS.match(line.strip())
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
    gap = 60
    if "--gap" in sys.argv:
        gap = int(sys.argv[sys.argv.index("--gap") + 1])
    titles = [a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()]
    songs = json.load(open(SONGS, encoding="utf-8"))
    want = [s for s in songs if s["title"] in titles]
    print("处理 %d 首: %s (gap=%ds)" % (len(want), "、".join(s["title"] for s in want), gap), flush=True)
    for n, s in enumerate(want, 1):
        j = jget("https://music.163.com/api/search/get/web",
                 {"s": "%s %s" % (s["title"], s.get("artist") or ""), "type": 1, "limit": 10}, gap)
        time.sleep(gap)
        best = pick(((j or {}).get("result") or {}).get("songs") or [],
                    s["title"], s.get("artist") or "", s["dur"])
        if not best:
            print("[%d/%d] MISS %s" % (n, len(want), s["title"]), flush=True)
            continue
        ly = jget("https://music.163.com/api/song/lyric",
                  {"id": best["id"], "lv": 1, "kv": 1, "tv": -1}, gap)
        time.sleep(gap)
        lines = parse(((ly or {}).get("lrc") or {}).get("lyric", ""))
        if len(lines) < 8:
            print("[%d/%d] NOLRC %s" % (n, len(want), s["title"]), flush=True)
            continue
        s["netease"] = best["id"]
        s["lrc"] = ((ly or {}).get("lrc") or {}).get("lyric", "")
        s["lyrics"] = [t for _x, t in lines]
        s["lyrics_from"] = "netease:%s" % best["id"]
        if (best.get("album") or {}).get("name"):
            s["album"] = best["album"]["name"]
        dur = s["dur"]
        ok = abs(lines[-1][0] - dur) <= 20 or lines[-1][0] > dur
        print("[%d/%d] OK %-22s %d行 末行%.0fs/%.0fs %s" % (
            n, len(want), s["title"], len(lines), lines[-1][0], dur,
            "可同步" if ok else "长度差太多"), flush=True)
        if ok:
            os.makedirs(SYNC, exist_ok=True)
            json.dump({"id": s["id"], "title": s["title"], "dur": dur,
                       "approx": abs(lines[-1][0] - dur) > 8,
                       "lines": [{"t": t, "s": txt} for t, txt in lines]},
                      open(os.path.join(SYNC, s["id"] + ".timing.json"), "w", encoding="utf-8"),
                      ensure_ascii=False)
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()
