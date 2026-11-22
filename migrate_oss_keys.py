# -*- coding: utf-8 -*-
"""把 OSS 上的音频对象从「歌名 id」改成 slug 文件名（服务端拷贝，不重新上传）。

tl128-music/media/<id>.m4a   →   tl128-music/media/<slug>.m4a

用法：
    python migrate_oss_keys.py --dry          # 只看会干什么
    python migrate_oss_keys.py                # 拷贝 + 校验
    python migrate_oss_keys.py --delete-old   # 校验通过后删掉旧对象
"""
import json
import os
import sys
import time

import oss2

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(ROOT, ".oss_key.json")
SONGS = os.path.join(ROOT, "data", "songs.json")
PREFIX = "tl128-music/media/"


def head(bucket, key):
    try:
        return retry(lambda: bucket.head_object(key))
    except oss2.exceptions.NotFound:
        return None


def retry(fn, n=5, wait=4):
    last = None
    for i in range(n):
        try:
            return fn()
        except oss2.exceptions.NotFound:
            raise
        except Exception as e:  # noqa: BLE001  网络抖动就重试
            last = e
            print("    重试 %d/%d: %s" % (i + 1, n, str(e)[:90]), flush=True)
            time.sleep(wait)
    raise last


def main():
    dry = "--dry" in sys.argv
    delete_old = "--delete-old" in sys.argv
    k = json.load(open(KEYFILE, encoding="utf-8"))
    auth = oss2.Auth(k["id"], k["secret"])
    bucket = oss2.Bucket(auth, "https://oss-cn-shanghai.aliyuncs.com", k["bucket"])
    songs = json.load(open(SONGS, encoding="utf-8"))

    copied = skipped = missing = 0
    for i, s in enumerate(songs, 1):
        slug = s.get("slug")
        if not slug:
            raise SystemExit("缺 slug: %s" % s["title"])
        src_key, dst_key = PREFIX + s["id"] + ".m4a", PREFIX + slug + ".m4a"
        src = head(bucket, src_key)
        if src is None:
            print("[%02d] 旧对象不存在：%s" % (i, src_key))
            missing += 1
            continue
        dst = head(bucket, dst_key)
        if dst is not None and int(dst.content_length) == int(src.content_length):
            skipped += 1
            print("[%02d] 已存在 %-46s %s" % (i, dst_key, dst.content_type))
            continue
        if dry:
            print("[%02d] 会拷贝 %s -> %s (%.1f MB)" % (i, s["id"], slug, int(src.content_length) / 1048576))
            continue
        retry(lambda: bucket.copy_object(k["bucket"], src_key, dst_key))
        retry(lambda: bucket.put_object_acl(dst_key, oss2.OBJECT_ACL_PUBLIC_READ))
        check = head(bucket, dst_key)
        ok = check is not None and int(check.content_length) == int(src.content_length)
        print("[%02d] %s %-46s %s %.1fMB" % (i, "ok " if ok else "ERR", dst_key,
                                             check.content_type if check else "-",
                                             int(src.content_length) / 1048576), flush=True)
        if not ok:
            raise SystemExit("拷贝校验失败: %s" % dst_key)
        copied += 1

    print("\n拷贝 %d，已存在 %d，旧对象缺失 %d" % (copied, skipped, missing))

    if delete_old and not dry:
        removed = 0
        for s in songs:
            old = PREFIX + s["id"] + ".m4a"
            if old == PREFIX + s["slug"] + ".m4a":
                continue
            if head(bucket, old) is not None:
                retry(lambda: bucket.delete_object(old))
                removed += 1
        print("已删除旧对象 %d 个" % removed)

    objs = sorted(o.key for o in oss2.ObjectIterator(bucket, prefix=PREFIX))
    print("现在 %s 下共 %d 个对象" % (PREFIX, len(objs)))
    for o in objs[:3]:
        print("  ", o)
    return objs


if __name__ == "__main__":
    main()


