# -*- coding: utf-8 -*-
"""生成星标候选清单（Markdown 勾选表）。

用法：
    python make_star_list.py          # 生成 星标候选.md
    python apply_stars.py             # 按勾选结果写回 songs.json
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
OUT = os.path.join(ROOT, "星标候选.md")


def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    lines = [
        "# 星标候选（42 首）",
        "",
        "把想推荐的那几首前面的 `[ ]` 改成 `[x]`（或者直接把序号告诉我），我按这个更新站点。",
        "",
        "- 打了星标的歌：列表里标题前面有 ★，首页顶部多一块「特零推荐」",
        "- 星星是**站点内容**，跟「收藏」不一样（收藏只在你自己的浏览器里）",
        "",
        "| ✔ | # | 歌名 | 原唱 | 时长 | 有无同步歌词 |",
        "|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(songs, 1):
        sync = "有" if s.get("star") is not None and os.path.exists(
            os.path.join(ROOT, "data", "sync", s["id"] + ".timing.json")) else ""
        sync = "有" if os.path.exists(os.path.join(ROOT, "data", "sync", s["id"] + ".timing.json")) else "—"
        mark = "x" if s.get("star") else " "
        lines.append("| [%s] | %d | %s | %s | %s | %s |" % (
            mark, i, s["title"], s.get("artist") or "", s.get("dur_txt") or
            "%d:%02d" % (int(s["dur"]) // 60, int(s["dur"]) % 60), sync))
    lines.append("")
    lines.append("共 %d 首，有同步歌词 %d 首。" % (
        len(songs),
        sum(1 for s in songs if os.path.exists(os.path.join(ROOT, "data", "sync", s["id"] + ".timing.json")))))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("已生成", OUT)


if __name__ == "__main__":
    main()
