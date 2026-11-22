# -*- coding: utf-8 -*-
"""把 42 首音频传到阿里云 OSS：hubingsf/tl128-music/media/

用法：python upload_oss.py [--dry]
已存在且大小一致的会跳过。
"""
import json
import os
import sys

import oss2

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(ROOT, ".oss_key.json")
SONGS = os.path.join(ROOT, "data", "songs.json")
SRC = r"E:\我唱的歌"


def main():
    dry = "--dry" in sys.argv
    k = json.load(open(KEYFILE, encoding="utf-8"))
    auth = oss2.Auth(k["id"], k["secret"])
    bucket = oss2.Bucket(auth, "https://oss-cn-shanghai.aliyuncs.com", k["bucket"])
    songs = json.load(open(SONGS, encoding="utf-8"))
    up = skip = 0
    total = 0
    for i, s in enumerate(songs, 1):
        src = os.path.join(SRC, s.get("file") or "")
        if not os.path.exists(src):
            print("[%02d/%d] 缺源文件 %s" % (i, len(songs), s.get("file")))
            continue
        size = os.path.getsize(src)
        key = "tl128-music/media/%s.m4a" % (s.get("slug") or s["id"])
        meta = None
        try:
            meta = bucket.head_object(key)
        except oss2.exceptions.NotFound:
            meta = None
        except Exception:  # noqa: BLE001
            meta = None
        if meta is not None and int(meta.content_length) == size:
            skip += 1
            total += size
            print("[%02d/%d] skip  %s" % (i, len(songs), s["id"]))
            continue
        if dry:
            print("[%02d/%d] would upload %s (%.1f MB)" % (i, len(songs), s["id"], size / 1048576))
            continue
        bucket.put_object_from_file(key, src, headers={
            "Content-Type": "audio/mp4",
            "Cache-Control": "public, max-age=31536000",
        })
        bucket.put_object_acl(key, oss2.OBJECT_ACL_PUBLIC_READ)
        up += 1
        total += size
        print("[%02d/%d] up    %s (%.1f MB)" % (i, len(songs), s["id"], size / 1048576), flush=True)
    print("\n上传 %d，跳过 %d，共 %.1f MB" % (up, skip, total / 1048576))


if __name__ == "__main__":
    main()
