# -*- coding: utf-8 -*-
"""按「歌名 + 原唱」严格匹配，从网易云重取歌词 / 专辑 / 封面 / 时间轴。

严格条件：歌名（去掉括号说明后）完全相同 + 原唱名字出现在歌曲的歌手列表里。
匹配不到就保留原数据，不瞎覆盖。

用法：python refetch_lyrics.py [--only 歌名1,歌名2] [--dry]
"""
import json
import os
import random
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
COVERS = os.path.join(ROOT, "data", "covers")
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


def artist_tokens(a):
    out = []
    for t in re.split(r"[、,，/]", a or ""):
        t = re.sub(r"[（(][^）)]*[）)]", "", t).strip()
        if t:
            out.append(norm(t))
    return [x for x in out if x]


def jget(url, params, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=25)
            j = r.json()
            if j.get("code") == 200:
                return j
            print("   code %s retry %d" % (j.get("code"), i + 1))
        except Exception as e:  # noqa: BLE001
            print("   err %s retry %d" % (e, i + 1))
        time.sleep(6 + i * 6)
    return None


def parse_lrc(lrc):
    out = []
    for line in (lrc or "").split("\n"):
        line = line.strip()
        m = re.match(r"^\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$", line)
        if not m:
            continue
        mm, ss, frac, body = m.group(1), m.group(2), m.group(3) or "0", m.group(4).strip()
        if not body:
            continue
        t = int(mm) * 60 + int(ss) + int(frac.ljust(3, "0")) / 1000.0
        out.append((round(t, 2), body))
    return out


def plain(lines):
    """只去掉相邻重复行（副歌反复出现是正常的，不能全局去重）"""
    out = []
    for _t, s in lines:
        if BAD.search(s) and len(s) < 40:
            continue
        if out and out[-1] == s:
            continue
        out.append(s)
    return out


def pick(cands, title, artist, dur):
    nt, toks = norm(title), artist_tokens(artist)
    best, bs = None, -1
    for i, c in enumerate(cands):
        names = [norm(a.get("name")) for a in (c.get("artists") or [])]
        if norm(c.get("name")) != nt:
            continue
        hit = any(t and t in n for t in toks for n in names)
        if not hit:
            continue
        score = 10 - i * 0.3
        d = (c.get("duration") or 0) / 1000.0
        gap = abs(d - dur) if d else 999
        if gap <= 5:
            score += 6
        elif gap <= 15:
            score += 3
        elif gap <= 40:
            score += 1
        else:
            score -= 4
        if score > bs:
            best, bs = c, score
    return best, bs


def main():
    only = None
    dry = "--dry" in sys.argv
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    songs = json.load(open(SONGS, encoding="utf-8"))
    os.makedirs(COVERS, exist_ok=True)

    for n, s in enumerate(songs, 1):
        if only and s["title"] not in only:
            continue
        title, artist, dur = s["title"], s.get("artist") or "", s["dur"]
        j = jget("https://music.163.com/api/search/get/web",
                 {"s": "%s %s" % (title, artist), "type": 1, "limit": 10})
        cands = ((j or {}).get("result") or {}).get("songs") or []
        if not cands:
            j = jget("https://music.163.com/api/search/get/web",
                     {"s": title, "type": 1, "limit": 10})
            cands = ((j or {}).get("result") or {}).get("songs") or []
        best, score = pick(cands, title, artist, dur)
        if not best:
            print("[%02d/%d] MISS  %-28s（保持原样）" % (n, len(songs), s["id"]))
            time.sleep(2.5)
            continue
        sid = best["id"]
        d = jget("https://music.163.com/api/song/detail", {"ids": json.dumps([sid])})
        detail = ((d or {}).get("songs") or [{}])[0]
        album = (detail.get("album") or {})
        time.sleep(1.6)
        ly = jget("https://music.163.com/api/song/lyric",
                  {"id": sid, "lv": 1, "kv": 1, "tv": -1})
        time.sleep(1.6)
        lrc = ((ly or {}).get("lrc") or {}).get("lyric", "")
        lines = parse_lrc(lrc)
        if len(lines) < 4:
            print("[%02d/%d] NOLRC %-28s（保持原样）" % (n, len(songs), s["id"]))
            time.sleep(2)
            continue

        old_len = len(s.get("lyrics") or [])
        s["netease"] = sid
        s["lrc"] = lrc
        s["lyrics"] = plain(lines)
        s["lyrics_from"] = "netease:%s" % sid
        if album.get("name"):
            s["album"] = album["name"]
        if album.get("picUrl"):
            pic = album["picUrl"] + "?param=600y600"
            try:
                img = requests.get(pic, headers=H, timeout=30)
                if img.ok and len(img.content) > 5000:
                    open(os.path.join(COVERS, s["id"] + ".jpg"), "wb").write(img.content)
                    s["cover"] = "assets/covers/%s.jpg" % s["id"]
                    s["cover_from"] = "netease"
            except Exception as e:  # noqa: BLE001
                print("   cover err %s" % e)
        print("[%02d/%d] OK    %-28s %d→%d 行  末行%ss/dur%ss  《%s》" % (
            n, len(songs), s["id"], old_len, len(s["lyrics"]), lines[-1][0], dur,
            (album.get("name") or "")[:18]))
        if not dry:
            json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(random.uniform(2.5, 4.0))

    print("\n完成。有歌词 %d/%d" % (sum(1 for x in songs if x.get("lyrics")), len(songs)))


if __name__ == "__main__":
    main()

