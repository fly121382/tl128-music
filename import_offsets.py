# -*- coding: utf-8 -*-
"""把 align.html 导出的 offsets.json 收进来，写进 data/offsets.json。

用法：
    python import_offsets.py 偏移文件.json     # 合并（同名覆盖）
    python import_offsets.py 偏移文件.json --replace
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(ROOT, "data", "offsets.json")
SONGS = os.path.join(ROOT, "data", "songs.json")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法：python import_offsets.py <offsets.json> [--replace]")
    src = sys.argv[1]
    data = json.load(open(src, encoding="utf-8"))
    songs = {s["id"]: s for s in json.load(open(SONGS, encoding="utf-8"))}
    cur = {}
    if os.path.exists(DST) and "--replace" not in sys.argv:
        cur = json.load(open(DST, encoding="utf-8"))

    added, unknown = 0, []
    for k, v in data.items():
        if k not in songs:
            unknown.append(k)
            continue
        cur[k] = round(float(v), 1)
        added += 1
    json.dump(cur, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              sort_keys=True)
    print("写入 %d 条偏移，共 %d 条 → %s" % (added, len(cur), DST))
    for k in sorted(cur, key=lambda x: abs(cur[x]), reverse=True):
        print("  %-30s %+0.1fs" % (k, cur[k]))
    if unknown:
        print("\n对不上的 id（忽略）：", ", ".join(unknown))


if __name__ == "__main__":
    main()
