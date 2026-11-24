# -*- coding: utf-8 -*-
"""把 600×600 的封面压成 400×400 / q82，传到 OSS：tl128-music-audio/tl128-music/covers/<slug>.jpg

GitHub Pages 在国内拉 42 张封面要几十秒（实测 ~25 KB/s），阿里云上海几十毫秒，所以封面也搬 OSS。

用法：
  python make_covers.py            # 只生成 data/covers_opt/
  python make_covers.py --upload   # 生成 + 传到 OSS（大小一致会跳过）
"""
import json
import os
import sys

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SRC_DIR = os.path.join(ROOT, "data", "covers")
OUT_DIR = os.path.join(ROOT, "data", "covers_opt")
SIZE = 400
QUALITY = 82
KEYFILE = os.path.join(ROOT, ".oss_key.json")
CONFIG = os.path.join(ROOT, "config.json")


def build():
    songs = json.load(open(SONGS, encoding="utf-8"))
    os.makedirs(OUT_DIR, exist_ok=True)
    before = after = 0
    made = []
    for s in songs:
        src = os.path.join(SRC_DIR, s["id"] + ".jpg")
        if not os.path.exists(src):
            print("!! 缺封面源文件：%s" % s["id"])
            continue
        dst = os.path.join(OUT_DIR, (s.get("slug") or s["id"]) + ".jpg")
        before += os.path.getsize(src)
        im = Image.open(src).convert("RGB")
        im = ImageOps.fit(im, (SIZE, SIZE), Image.LANCZOS)
        im.save(dst, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        after += os.path.getsize(dst)
        made.append((s.get("slug") or s["id"], os.path.getsize(dst)))
    print("封面 %d 张：%.1f MB → %.2f MB（平均 %.0f KB）"
          % (len(made), before / 1048576, after / 1048576,
             after / max(1, len(made)) / 1024))
    return made


def upload():
    import oss2

    k = json.load(open(KEYFILE, encoding="utf-8"))
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    bucket = oss2.Bucket(oss2.Auth(k["id"], k["secret"]),
                         "https://oss-cn-shanghai.aliyuncs.com",
                         cfg.get("ossBucket") or k["bucket"])
    up = skip = 0
    for name in sorted(os.listdir(OUT_DIR)):
        if not name.endswith(".jpg"):
            continue
        path = os.path.join(OUT_DIR, name)
        key = "tl128-music/covers/" + name
        size = os.path.getsize(path)
        try:
            if int(bucket.head_object(key).content_length) == size:
                skip += 1
                continue
        except Exception:  # noqa: BLE001
            pass
        bucket.put_object_from_file(key, path, headers={
            "Content-Type": "image/jpeg",
            "Cache-Control": "public, max-age=31536000",
        })
        bucket.put_object_acl(key, oss2.OBJECT_ACL_PUBLIC_READ)
        up += 1
    print("封面上传 %d，跳过 %d" % (up, skip))


if __name__ == "__main__":
    build()
    if "--upload" in sys.argv:
        upload()
