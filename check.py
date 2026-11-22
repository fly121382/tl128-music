# -*- coding: utf-8 -*-
"""发站前的自检：媒体/封面/数据/播客/站点地图是否齐全。

用法：python check.py [docs目录]
"""
import json
import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs")


def main():
    bad = []
    songs = json.load(open(os.path.join(ROOT, "data", "songs.json"), encoding="utf-8"))
    print("歌曲数：%d" % len(songs))

    no_artist = [s["title"] for s in songs if not (s.get("artist") or "").strip()]
    if no_artist:
        bad.append("缺原唱：%s" % ", ".join(no_artist))

    media_base = ""
    try:
        cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
        media_base = (cfg.get("mediaBase") or "").strip()
    except Exception:  # noqa: BLE001
        pass
    for s in songs:
        if media_base:
            continue
        media = os.path.join(OUT, "media", s["id"] + ".m4a")
        if not os.path.exists(media):
            bad.append("缺音频：%s" % s["id"])
        elif os.path.getsize(media) < 10000:
            bad.append("音频过小：%s" % s["id"])
        cov = os.path.join(OUT, "assets", "covers", s["id"] + ".jpg")
        if not os.path.exists(cov):
            bad.append("缺封面：%s" % s["id"])

    feed_path = os.path.join(OUT, "assets", "songs.json")
    feed = json.load(open(feed_path, encoding="utf-8"))
    if len(feed) != len(songs):
        bad.append("前端数据条数不对：%d" % len(feed))
    for f in feed:
        for key in ("id", "t", "a", "d", "c", "m", "l"):
            if key not in f:
                bad.append("前端数据缺字段 %s：%s" % (key, f.get("id")))
        if not media_base and not os.path.exists(os.path.join(OUT, urllib.parse.unquote(f["m"]))):
            bad.append("前端媒体路径无效：%s" % f["m"])
        if not os.path.exists(os.path.join(OUT, urllib.parse.unquote(f["c"]))):
            bad.append("前端封面路径无效：%s" % f["c"])

    # 播客
    pod = os.path.join(OUT, "podcast.xml")
    try:
        root = ET.parse(pod).getroot()
        items = root.find("channel").findall("item")
        if len(items) != len(songs):
            bad.append("播客条数不对：%d" % len(items))
        for it in items:
            enc = it.find("enclosure")
            url = enc.get("url") if enc is not None else ""
            if media_base:
                if not url.startswith(media_base + "/media/"):
                    bad.append("播客 enclosure 没指向 OSS：%s" % url)
            else:
                rel = urllib.parse.unquote(url.split("/media/")[-1]) if "/media/" in url else ""
                if not rel or not os.path.exists(os.path.join(OUT, "media", rel)):
                    bad.append("播客 enclosure 无效：%s" % url)
            if not (it.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}image") is not None):
                bad.append("播客缺封面：%s" % it.findtext("title"))
    except Exception as e:  # noqa: BLE001
        bad.append("podcast.xml 解析失败：%s" % e)

    # 单曲页 + sitemap
    for s in songs:
        page = os.path.join(OUT, "song", s["id"] + ".html")
        if not os.path.exists(page):
            bad.append("缺单曲页：%s" % s["id"])
    try:
        sm = ET.parse(os.path.join(OUT, "sitemap.xml")).getroot()
        locs = [el.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc") for el in sm]
        if len(locs) != len(songs) + 1:
            bad.append("sitemap 条数不对：%d" % len(locs))
    except Exception as e:  # noqa: BLE001
        bad.append("sitemap.xml 解析失败：%s" % e)

    # 关键资源
    for rel in ("index.html", "assets/style.css", "assets/app.js", "assets/songs.json",
                "assets/podcast-cover.jpg", "assets/icon.png", "CNAME", ".nojekyll",
                "tools/tapper.html"):
        if not os.path.exists(os.path.join(OUT, rel)):
            bad.append("缺文件：%s" % rel)

    n_ly = sum(1 for s in songs if s.get("lyrics"))
    size = sum(os.path.getsize(os.path.join(OUT, "media", s["id"] + ".m4a"))
               for s in songs if os.path.exists(os.path.join(OUT, "media", s["id"] + ".m4a")))
    print("歌词：%d/%d 首" % (n_ly, len(songs)))
    print("媒体体积：%.1f MB" % (size / 1048576))
    print("CNAME：%s" % open(os.path.join(OUT, "CNAME"), encoding="utf-8").read().strip())
    if bad:
        print("\n发现 %d 个问题：" % len(bad))
        for b in bad[:40]:
            print(" -", b)
        sys.exit(1)
    print("\n全部检查通过。")


if __name__ == "__main__":
    main()


