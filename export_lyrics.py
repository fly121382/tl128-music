# -*- coding: utf-8 -*-
"""把站上「对过轴」的歌词导出成 LRC + SRT，直接放在音频旁边（同名不同后缀）。

时间轴来源：
  data/sync/<id>.timing.json 里的 {t, s}
  data/offsets.json 里每首的整体偏移 o
站上的显示时刻 = t - o（app.js: currentTime + 0.15 + o 命中 t，0.15 是 UI 的视觉提前量）
所以导出时间 = t - o，负数截到 0。

用法：
  python export_lyrics.py            # 写到 E:\\我唱的歌
  python export_lyrics.py --dry

产物：E:\\我唱的歌\\<歌名>.lrc（音乐播放器用）
      E:\\我唱的歌\\字幕\\<歌名>.srt（剪辑用；放子目录是因为 VLC 会把同目录所有
      srt 都挂成字幕轨，42 首放一起就变成 42 条轨）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SYNC = os.path.join(ROOT, "data", "sync")
OFFSETS = os.path.join(ROOT, "data", "offsets.json")
OUT = r"E:\我唱的歌"


def mmss(sec, sep=":"):
    m = int(sec // 60)
    s = sec - m * 60
    return "%02d%s%05.2f" % (m, sep, s)


def srt_time(sec):
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")


def main():
    dry = "--dry" in sys.argv
    songs = json.load(open(SONGS, encoding="utf-8"))
    offs = json.load(open(OFFSETS, encoding="utf-8")) if os.path.exists(OFFSETS) else {}

    made_lrc = made_srt = 0
    total_dropped = 0
    problems = []
    for s in songs:
        tp = os.path.join(SYNC, s["id"] + ".timing.json")
        if not os.path.exists(tp):
            problems.append("%s：没有打点文件" % s["title"])
            continue
        tj = json.load(open(tp, encoding="utf-8"))
        o = float(offs.get(s["id"], 0) or 0)
        dur = float(s["dur"])

        rows = []
        dropped = 0
        for ln in tj.get("lines", []):
            if ln.get("t") is None:
                continue
            txt = (ln.get("s") or "").strip()
            if not txt:
                continue
            t = round(float(ln["t"]) - o, 2)
            if t < -0.3:
                # 偏移之后落在音频开始之前比较远的行（基本都是作词/作曲/制作人这类制作信息）
                dropped += 1
                continue
            if t < 0:
                t = 0.0
            rows.append((t, txt))
        if not rows:
            problems.append("%s：偏移后没有可用的歌词行" % s["title"])
            continue

        src = os.path.join(OUT, s.get("file") or "")
        if not os.path.exists(src):
            problems.append("%s：音频不在 %s" % (s["title"], OUT))
        base = os.path.splitext(os.path.basename(s.get("file") or s["id"]))[0]

        # ---- LRC
        lrc = ["[ti:%s]" % s["title"], "[ar:特零128]",
               "[al:我唱的歌]", "[by:特零128]",
               "[length:%02d:%02d]" % (int(dur // 60), int(dur % 60)),
               "[offset:0]", ""]
        for t, txt in rows:
            lrc.append("[%s]%s" % (mmss(t), txt))
        lrc_path = os.path.join(OUT, base + ".lrc")

        # ---- SRT（结束时间取下一句开始，最长 8s、不超过音频长度；间隔太小的句子不重叠）
        srt = []
        for i, (t, txt) in enumerate(rows):
            nxt = rows[i + 1][0] if i + 1 < len(rows) else t + 3.5
            end = min(nxt, t + 8.0)
            if dur > t:
                end = min(end, dur)
            if end <= t + 0.03:
                end = t + 0.03
            srt.append("%d\n%s --> %s\n%s\n" % (i + 1, srt_time(t), srt_time(end), txt))
        srt_path = os.path.join(OUT, "字幕", base + ".srt")

        if not dry:
            os.makedirs(os.path.join(OUT, "字幕"), exist_ok=True)
            with open(lrc_path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("\n".join(lrc) + "\n")
            with open(srt_path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("\n".join(srt))
        made_lrc += 1
        made_srt += 1
        total_dropped += dropped

        if rows[-1][0] > dur:
            problems.append("%s：最后一句 %.1fs 超过音频长度 %.1fs（会播不到）"
                            % (s["title"], rows[-1][0], dur))

    print("导出 LRC %d 个、SRT %d 个 → %s" % (made_lrc, made_srt, OUT))
    print("其中 %d 行因整体偏移后落在 0 秒之前被丢掉（作词/作曲/制作信息一类）" % total_dropped)
    if problems:
        print("注意：")
        for p in problems:
            print("  -", p)


if __name__ == "__main__":
    main()

