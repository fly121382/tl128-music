# -*- coding: utf-8 -*-
"""tl128 音乐站生成器。

用法：
    python build.py               # 生成到 docs/
    python build.py --out <dir>

结构：data/songs.json（由 fetch_meta.py / collect.py 生成）+ assets/ + templates/
产物：单页播放器（docs/index.html）、每首歌的分享页、播客 RSS、sitemap、CNAME。
音频从 config.source 硬链接进 docs/media/，不重复占空间。
"""
import argparse
import html
import json
import os
import re
import shutil
import urllib.parse
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
ASSETS = os.path.join(ROOT, "assets")
TEMPLATES = os.path.join(ROOT, "templates")
DEFAULT_OUT = os.path.join(ROOT, "docs")


def mmss(sec):
    sec = int(round(sec))
    return "%d:%02d" % (sec // 60, sec % 60)


def link_or_copy(src, dst):
    try:
        if os.path.exists(dst):
            os.remove(dst)
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def brand_images(cfg, out_dir):
    """播客封面 + 站点图标（缺了才生成）。"""
    from PIL import Image, ImageDraw, ImageFont

    def font(size, bold=False):
        for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
                  r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue
        return ImageFont.load_default()

    def make(path, size, big, small):
        img = Image.new("RGB", (size, size), "#16181c")
        d = ImageDraw.Draw(img)
        for i in range(size):
            c = int(20 + 24 * i / size)
            d.line([(0, i), (size, i)], fill=(c, c - 1, c - 3))
        band = int(size * 0.30)
        d.rectangle([0, 0, size, band], fill="#c2410c")
        f1 = font(int(size * 0.155), True)
        f2 = font(int(size * 0.050))
        d.text((size * 0.08, size * 0.085), big, font=f1, fill="#fffaf5")
        d.text((size * 0.085, size * 0.325), small, font=f2, fill="#f0cbb4")
        d.line([(size * 0.085, size * 0.72), (size * 0.30, size * 0.72)],
               fill="#c2410c", width=max(2, size // 220))
        d.text((size * 0.08, size * 0.76), "特零128", font=font(int(size * 0.085), True),
               fill="#eceae6")
        img.save(path, quality=92)

    cover = os.path.join(out_dir, "assets", "podcast-cover.jpg")
    make(cover, 1400, "我唱的歌", "42 首翻唱 · 138 分钟")
    icon = os.path.join(out_dir, "assets", "icon.png")
    if not os.path.exists(icon):
        make(icon, 256, "歌", "特零128")
    # 播放器在没选歌时的占位图：不要把 130 KB 的 icon.png 塞进首屏
    make(os.path.join(out_dir, "assets", "placeholder.jpg"), 160, "歌", "特零128")
    return cover, icon


def build_podcast(cfg, songs, base):
    out = []
    for s in songs:
        desc = "《%s》 原唱：%s ｜ 翻唱：特零128" % (s["title"], s["artist"])
        out.append(
            "<item><title>%s</title>"
            "<description>%s</description>"
            '<enclosure url="%s" length="%d" type="audio/mp4"/>'
            "<guid isPermaLink=\"false\">%s</guid>"
            "<pubDate>%s</pubDate>"
            "<itunes:duration>%s</itunes:duration>"
            "<itunes:author>%s</itunes:author>"
            '<itunes:image href="%s"/>'
            "</item>"
            % (html.escape(s["title"]), html.escape(desc), s["media_url"], s["size"],
               html.escape(s["id"]), s["_pubdate"], mmss(s["dur"]),
               html.escape(cfg["singer"]), s["cover_url"]))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">'
        "<channel>"
        "<title>%s</title><link>%s/</link><language>zh-CN</language>"
        "<description>%s</description>"
        "<itunes:author>%s</itunes:author>"
        '<itunes:image href="%s/assets/podcast-cover.jpg"/>'
        "<itunes:category text=\"Music\"/><itunes:explicit>false</itunes:explicit>"
        "<itunes:summary>%s</itunes:summary>%s</channel></rss>"
        % (html.escape(cfg["title"]), base, html.escape(cfg["description"]),
           html.escape(cfg["singer"]), base, html.escape(cfg["description"]), "".join(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--base", default=None)
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    base = (args.base or cfg["baseUrl"]).rstrip("/")
    out_dir = args.out or DEFAULT_OUT
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    for d in ("assets", "assets/covers", "media", "song"):
        os.makedirs(os.path.join(out_dir, d), exist_ok=True)

    songs = json.load(open(os.path.join(DATA, "songs.json"), encoding="utf-8"))
    songs.sort(key=lambda s: s["id"])
    src_dir = cfg.get("source", "")

    for s in songs:
        s["dur_txt"] = mmss(s["dur"])
        # 音频文件名用 ASCII slug（老外/手机播放器里不会变乱码），不写 slug 的旧数据回落到 id
        s["media_file"] = (s.get("slug") or s["id"]) + ".m4a"
        media_base = (cfg.get("mediaBase") or "").rstrip("/")
        if media_base:
            s["media_url"] = "%s/media/%s" % (media_base, urllib.parse.quote(s["media_file"]))
            s["media_rel"] = s["media_url"]
        else:
            s["media_url"] = "%s/media/%s" % (base, urllib.parse.quote(s["media_file"]))
            s["media_rel"] = "media/" + urllib.parse.quote(s["media_file"])
        # 封面也放 OSS：GitHub Pages 在国内拉 42 张图要几十秒（实测 ~25 KB/s），阿里云上海几十毫秒
        # 想退回「封面放 GitHub Pages」就把 config.json 的 coverBase 设成 false
        raw_cover_base = cfg.get("coverBase", None)
        if raw_cover_base is False:
            cover_base = ""
        elif raw_cover_base:
            cover_base = raw_cover_base.rstrip("/")
        elif media_base:
            cover_base = media_base + "/covers"
        else:
            cover_base = ""
        if cover_base:
            s["cover_url"] = "%s/%s" % (cover_base, urllib.parse.quote(s["media_file"][:-4] + ".jpg"))
            s["cover_rel"] = s["cover_url"]
            # 列表里只显示 44px，用 OSS 实时缩图（3 KB vs 25 KB）
            s["thumb_url"] = s["cover_url"] + "?x-oss-process=image/resize,w_120/quality,q_82"
        else:
            s["cover_url"] = "%s/%s" % (base, urllib.parse.quote(s.get("cover") or "assets/icon.png"))
            s["cover_rel"] = urllib.parse.quote(s.get("cover") or "assets/icon.png")
            s["thumb_url"] = s["cover_url"]
        # 单曲页/分享链接用 ASCII slug（中文歌名在链接里会被百分号编码成一串 %E4%B8%8B…）
        if not s.get("slug"):
            print("!! 这首歌没有 slug，链接会退回中文名：%s（跑 python make_slugs.py --write）" % s["title"])
            s["slug"] = s["id"]
        s["url"] = "%s/#/song/%s" % (base, urllib.parse.quote(s["slug"]))
        s["page"] = "song/%s.html" % urllib.parse.quote(s["slug"])
        s["pubdate"] = datetime(2026, 11, 23, tzinfo=timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S +0000")
        s["_pubdate"] = s["pubdate"]

        if (cfg.get("mediaBase") or "").strip():
            pass  # 音频托管在 OSS，仓库里不放
        else:
            src = os.path.join(src_dir, s.get("file") or "")
            if os.path.exists(src):
                link_or_copy(src, os.path.join(out_dir, "media", s["media_file"]))
            else:
                print("!! 缺少音频: %s" % s.get("file"))
        cov = os.path.join(DATA, "covers", s["id"] + ".jpg")
        if not cover_base and os.path.exists(cov):
            # 封面走本地时就照旧拷进 docs；走 OSS 时不进仓库（省 4.7 MB）
            link_or_copy(cov, os.path.join(out_dir, "assets", "covers", s["id"] + ".jpg"))

    shutil.copytree(ASSETS, os.path.join(out_dir, "assets"), dirs_exist_ok=True)
    netease = os.path.join(DATA, "netease.json")
    if os.path.exists(netease):
        shutil.copy2(netease, os.path.join(out_dir, "assets", "netease.json"))
    tools_dir = os.path.join(ROOT, "tools")
    if os.path.isdir(tools_dir):
        shutil.copytree(tools_dir, os.path.join(out_dir, "tools"), dirs_exist_ok=True)
    brand_images(cfg, out_dir)

    # ---- 前端用的数据（含歌词、同步时间轴、对齐偏移）
    sync_dir = os.path.join(DATA, "sync")
    offsets = {}
    offsets_path = os.path.join(DATA, "offsets.json")
    if os.path.exists(offsets_path):
        try:
            offsets = json.load(open(offsets_path, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print("!! offsets.json 读不了：%s" % e)
    feed = []
    nsync = 0
    for s in songs:
        sync = None
        approx = False
        tp = os.path.join(sync_dir, s["id"] + ".timing.json")
        if os.path.exists(tp):
            try:
                tj = json.load(open(tp, encoding="utf-8"))
                sync = [[round(float(l["t"]), 2), l["s"]] for l in tj.get("lines", [])
                        if l.get("t") is not None]
                approx = bool(tj.get("approx"))
                if len(sync) < 2:
                    sync = None
            except Exception as e:  # noqa: BLE001
                print("!! 打点文件读不了 %s: %s" % (tp, e))
        if sync:
            nsync += 1
        feed.append({
            "id": s["id"], "sl": s["slug"], "t": s["title"], "a": s.get("artist") or "佚名",
            "al": s.get("album") or "", "d": s["dur"], "dt": s["dur_txt"],
            "c": s["cover_rel"], "th": s["thumb_url"], "m": s["media_rel"], "sz": s["size"], "kb": s["kbps"],
            "l": s.get("lyrics") or [], "y": sync, "ya": approx if sync else False,
            "o": float(offsets.get(s["id"]) or 0),
            "tr": s.get("tr") or None, "star": bool(s.get("star")),
            "kd": (s.get("kg") or {}).get("date") or "",
            "kv": (s.get("kg") or {}).get("versions") or 0,
        })
    json.dump(feed, open(os.path.join(out_dir, "assets", "songs.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(base=base, cfg=cfg)

    tpl_index = env.get_template("index.html")
    tpl_song = env.get_template("song.html")

    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(
        tpl_index.render(songs=songs, total=len(songs),
                         total_min=round(sum(s["dur"] for s in songs) / 60),
                         page_title=None))

    for s in songs:
        open(os.path.join(out_dir, "song", s["slug"] + ".html"),
             "w", encoding="utf-8").write(
            tpl_song.render(s=s, page_title=s["title"], total=len(songs)))
        # 老链接（song/<歌名>.html）不能 404：留一个跳转壳
        if s["slug"] != s["id"]:
            open(os.path.join(out_dir, "song", s["id"] + ".html"),
                 "w", encoding="utf-8").write(
                '<!doctype html><meta charset="utf-8">'
                '<title>%s</title><link rel="canonical" href="%s">'
                '<meta name="robots" content="noindex">'
                '<script>location.replace(%s);</script>'
                '<p>正在跳转…<a href="%s">%s</a></p>\n'
                % (html.escape(s["title"]), html.escape(s["url"]),
                   json.dumps(s["url"], ensure_ascii=False), html.escape(s["url"]),
                   html.escape(s["title"])))

    open(os.path.join(out_dir, "podcast.xml"), "w", encoding="utf-8").write(
        build_podcast(cfg, songs, base))

    urls = [base + "/"] + ["%s/song/%s.html" % (base, urllib.parse.quote(s["slug"])) for s in songs]
    open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join("<url><loc>%s</loc></url>" % html.escape(u) for u in urls) + "</urlset>")

    open(os.path.join(out_dir, "CNAME"), "w", encoding="utf-8").write(
        cfg["baseUrl"].split("//")[-1].split("/")[0] + "\n")
    open(os.path.join(out_dir, ".nojekyll"), "w", encoding="utf-8").write("")

    print("songs : %d（%d 分钟，%.1f MB）" % (
        len(songs), round(sum(s["dur"] for s in songs) / 60),
        sum(s["size"] for s in songs) / 1048576))
    print("lyrics: %d 首有歌词（%d 首已同步）" % (sum(1 for s in songs if s.get("lyrics")), nsync))
    print("out   : %s" % out_dir)


if __name__ == "__main__":
    main()


