# -*- coding: utf-8 -*-
"""给 42 首歌生成 ASCII slug（只打印，不改文件）。

规则：
  - 英文/数字保留，小写，空格和符号统一成连字符
  - 中文走拼音，一个字一节
  - 日文假名/特殊符号无法机械转写，用人工表（MANUAL）
  - 结果只允许 [a-z0-9-]，且必须唯一
"""
import json
import re
import sys
import unicodedata

from pypinyin import lazy_pinyin

sys.stdout.reconfigure(encoding="utf-8")

SONGS = r"E:\DSHwork\tl128-music\data\songs.json"

# 人工转写：歌名 → slug（日文、带特殊符号的）
MANUAL = {
    "Departures ～あなたにおくるアイの歌～": "departures-anata-ni-okuru-ai-no-uta",
    "別の人の彼女になったよ": "betsu-no-hito-no-kanojo-ni-natta-yo",
    "心做し": "kokoro-nashi",
    "反方向的钟 (Live)": "fan-fang-xiang-de-zhong-live",
}


def fold(text):
    # 全角 → 半角
    out = []
    for ch in text:
        o = ord(ch)
        if o == 0x3000:
            out.append(" ")
        elif 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif 0x301C <= o <= 0x301C or ch == "\u301c":  # 〜
            out.append("-")
        else:
            out.append(ch)
    return "".join(out)


def slugify(title):
    if title in MANUAL:
        return MANUAL[title]
    t = fold(title)
    # 括号里是 Live/伴奏 之类，保留语义
    t = re.sub(r"[()\[\]（）【】「」]", " ", t)
    t = unicodedata.normalize("NFKC", t)

    def cn(m):
        return "-".join(sum((lazy_pinyin(c) for c in m.group(0)), []))

    t = re.sub(r"[\u3400-\u9fff]+", cn, t).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return re.sub(r"-{2,}", "-", t).strip("-")


def main():
    write = "--write" in sys.argv
    songs = json.load(open(SONGS, encoding="utf-8"))
    seen = {}
    rows = []
    bad = []
    for s in songs:
        old = s.get("slug")
        sl = old or slugify(s["title"])
        if not sl or not re.fullmatch(r"[a-z0-9-]+", sl):
            bad.append((s["title"], sl))
        if sl in seen:
            bad.append(("重复: %s / %s" % (seen[sl], s["title"]), sl))
        seen[sl] = s["title"]
        rows.append((s["title"], sl, len(sl), bool(old)))
        # 只补缺的，不覆盖手写过的（日文/特殊符号靠 MANUAL 或手动改）
        if not old:
            s["slug"] = sl
    for t, sl, n, had in rows:
        print("%-42s -> %-46s %2d%s" % (t, sl, n, "" if had else "  (新生成)"))
    print()
    print("共 %d 首，最长 %d 字符，重复/非法 %d 个" % (len(rows), max(r[2] for r in rows), len(bad)))
    for b in bad:
        print("  !!", b)
    if bad:
        raise SystemExit("有非法 slug，未写入")
    if write:
        json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("已写入 %s" % SONGS)


if __name__ == "__main__":
    main()
