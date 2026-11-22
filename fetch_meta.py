# -*- coding: utf-8 -*-
"""抓歌单元数据：读 m4a 标签 → 搜网易云 → 取专辑封面 + 歌词。

用法：
    python fetch_meta.py            # 全量（已有结果会复用）
    python fetch_meta.py --force    # 全部重抓

产物：data/songs.json、data/covers/*.jpg
"""
import json
import os
import re
import subprocess
import sys
import time

import requests

SRC = r"E:\我唱的歌"
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
COVERS = os.path.join(DATA, "covers")
SONGS = os.path.join(DATA, "songs.json")

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://music.163.com/",
}


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-of", "json", path],
        capture_output=True, text=True, encoding="utf-8")
    fmt = json.loads(out.stdout)["format"]
    tags = fmt.get("tags", {})
    return {
        "title": tags.get("title", ""),
        "comment": tags.get("comment", ""),
        "dur": round(float(fmt["duration"]), 1),
        "size": int(fmt["size"]),
        "kbps": round(int(fmt["bit_rate"]) / 1000),
    }


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"[～~·・\s\-_/、，,。.！!？?'\"“”\[\]]", "", s)
    return s


def search(q, limit=8):
    r = requests.get("https://music.163.com/api/search/get/web",
                     params={"s": q, "type": 1, "limit": limit}, headers=H, timeout=20)
    j = r.json()
    return ((j.get("result") or {}).get("songs") or [])


def pick(songs, title, artist):
    best, bestscore = None, -1.0
    tt = norm(title)
    for i, s in enumerate(songs):
        names = " ".join(a["name"] for a in s.get("artists", []))
        t = norm(s.get("name"))
        score = 0.0
        if tt and t == tt:
            score += 5
        elif tt and tt in t:
            score += 3
        elif t and t in tt:
            score += 2
        for a in re.split(r"[、,，/]", artist or ""):
            a = a.strip()
            if a and norm(a) and norm(a) in norm(names):
                score += 4
                break
        score -= i * 0.1
        if score > bestscore:
            best, bestscore = s, score
    return best, bestscore


def detail(sid):
    r = requests.get("https://music.163.com/api/song/detail",
                     params={"ids": json.dumps([sid])}, headers=H, timeout=20)
    songs = r.json().get("songs") or []
    return songs[0] if songs else None


def lyric(sid):
    r = requests.get("https://music.163.com/api/song/lyric",
                     params={"id": sid, "lv": 1, "kv": 1, "tv": -1},
                     headers=H, timeout=20)
    j = r.json()
    return (j.get("lrc") or {}).get("lyric", ""), (j.get("tlyric") or {}).get("lyric", "")


def plain(lrc):
    """LRC → 纯文本行（去掉时间码与空行）。"""
    out = []
    for line in (lrc or "").split("\n"):
        line = re.sub(r"^\s*\[\d{1,2}:\d{1,2}[.:]\d{1,3}\]\s*", "", line).rstrip()
        line = re.sub(r"^\s*\[[a-zA-Z]+:.*?\]\s*$", "", line)
        if not line.strip():
            continue
        if line.strip() in ("纯音乐，请欣赏", "暂无歌词"):
            continue
        out.append(line.strip())
    return out


def slugify(title):
    s = title.strip()
    s = re.sub(r'[\\/:*?"<>|\s]+', "-", s)
    s = s.strip("-")
    return s or "song"


def main():
    force = "--force" in sys.argv
    os.makedirs(COVERS, exist_ok=True)
    old = {}
    if os.path.exists(SONGS) and not force:
        old = {x["title"]: x for x in json.load(open(SONGS, encoding="utf-8"))}

    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith((".m4a", ".mp3")))
    songs, used = [], set()
    for n, fn in enumerate(files, 1):
        path = os.path.join(SRC, fn)
        info = probe(path)
        title = info["title"].strip() or os.path.splitext(fn)[0]
        m = re.search(r"原唱[：:]\s*(.+?)\s*(?:｜|\||$)", info["comment"] or "")
        artist = m.group(1).strip() if m else ""
        slug = slugify(title)
        base, k = slug, 2
        while slug in used:
            slug = "%s-%d" % (base, k)
            k += 1
        used.add(slug)

        rec = {
            "id": slug, "title": title, "artist": artist, "singer": "特零128",
            "dur": info["dur"], "size": info["size"], "kbps": info["kbps"],
            "album": "", "netease": 0, "cover": "", "lyrics": [], "lrc": "", "match": 0,
            "file": fn,
        }
        prev = old.get(title)
        if prev and not force and prev.get("cover") and prev.get("lyrics"):
            prev.update({"dur": info["dur"], "size": info["size"], "kbps": info["kbps"]})
            rec = prev
            songs.append(rec)
            print("[%02d/%d] cached  %s" % (n, len(files), slug))
            continue

        try:
            cands = search("%s %s" % (title, artist))
            best, score = pick(cands, title, artist)
        except Exception as e:  # noqa: BLE001
            best, score, cands = None, -1, []
            print("search fail %s: %s" % (slug, e))
        if best and score >= 3:
            sid = best["id"]
            rec["netease"] = sid
            rec["album"] = (best.get("album") or {}).get("name", "")
            rec["match"] = round(score, 1)
            try:
                d = detail(sid)
                pic = ((d or {}).get("album") or {}).get("picUrl", "")
                if pic:
                    url = pic + "?param=600y600"
                    img = requests.get(url, headers=H, timeout=30)
                    if img.ok and len(img.content) > 5000:
                        cp = os.path.join(COVERS, slug + ".jpg")
                        open(cp, "wb").write(img.content)
                        rec["cover"] = "assets/covers/%s.jpg" % slug
            except Exception as e:  # noqa: BLE001
                print("cover fail %s: %s" % (slug, e))
            try:
                lrc, tlrc = lyric(sid)
                rec["lrc"] = lrc
                rec["lyrics"] = plain(lrc)
                if tlrc:
                    rec["tlyric"] = plain(tlrc)
            except Exception as e:  # noqa: BLE001
                print("lyric fail %s: %s" % (slug, e))
        songs.append(rec)
        print("[%02d/%d] %-6s cover=%d lyrics=%d  %s" %
              (n, len(files), round(score, 1), bool(rec["cover"]), len(rec["lyrics"]), slug))
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(0.8)

    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ncov = sum(1 for s in songs if s["cover"])
    nlyr = sum(1 for s in songs if s["lyrics"])
    total = sum(s["dur"] for s in songs)
    print("\nsongs=%d  cover=%d  lyrics=%d  total=%.1f min  size=%.1f MB"
          % (len(songs), ncov, nlyr, total / 60, sum(s["size"] for s in songs) / 1048576))


if __name__ == "__main__":
    main()
