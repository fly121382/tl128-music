# -*- coding: utf-8 -*-
"""把歌词做成双语：外文行下面配中文。

- data/trans.json：手工译文（按行对齐，空串表示不译）
- Dance Monkey 这种「原文 / 译文」挤在同一行的，自动拆成两行显示

用法：python apply_trans.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
TRANS = os.path.join(ROOT, "data", "trans.json")
CJK = re.compile(r"[\u4e00-\u9fff]")


def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    manual = json.load(open(TRANS, encoding="utf-8"))
    report = []

    for s in songs:
        lyrics = list(s.get("lyrics") or [])
        tr = None

        # 1) 手工译文
        if s["id"] in manual:
            arr = manual[s["id"]]
            if len(arr) != len(lyrics):
                report.append("%s 译文行数不符：%d vs %d" % (s["id"], len(arr), len(lyrics)))
            else:
                tr = arr

        # 2) 「原文 / 译文」同行 → 拆开
        if tr is None:
            parts = [l.split(" / ", 1) if " / " in l else None for l in lyrics]
            if sum(1 for p in parts if p and CJK.search(p[1])) >= 4:
                new_l, new_t = [], []
                for l, p in zip(lyrics, parts):
                    if p and CJK.search(p[1]) and not CJK.search(p[0]):
                        new_l.append(p[0].strip())
                        new_t.append(p[1].strip())
                    else:
                        new_l.append(l)
                        new_t.append("")
                s["lyrics"] = new_l
                tr = new_t
                report.append("%s 拆分双语 %d 行" % (s["id"], sum(1 for x in new_t if x)))

        keep = s.get("tr") if len(s.get("tr") or []) == len(s["lyrics"]) else None
        s["tr"] = tr if (tr and any(x.strip() for x in tr)) else keep
        if s["tr"]:
            report.append("%s：%d 行有译文" % (s["id"], sum(1 for x in s["tr"] if x.strip())))

    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(report) or "没有可处理的")

    # 顺带列出所有「非中文歌词」的歌，方便以后补
    foreign = []
    for s in songs:
        body = [l for l in (s.get("lyrics") or []) if not re.match(r"^(作词|作曲|编曲)", l)]
        if not body:
            continue
        cjk = sum(1 for l in body if CJK.search(l))
        if cjk / len(body) < 0.2:
            foreign.append((s["id"], cjk, len(body), bool(s.get("tr"))))
    print("\n歌里几乎没有中文的：")
    for x in foreign:
        print("  %-30s 中文行 %d/%d  译文=%s" % x)


if __name__ == "__main__":
    main()

