# -*- coding: utf-8 -*-
"""手册修正两首：
- 送别：换成都市版（朴树《厨子戏子痞子》片尾曲，168s，和录音 173s 最接近）
- 大风吹：网易云那版时间轴末行 214s、录音 236s（尾部是纯器乐），属于同一版，直接挂上
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.join(ROOT, "data", "songs.json")
SYNC = os.path.join(ROOT, "data", "sync")

SONGBIE_LRC = """[00:00.000] 作词 : 李叔同
[00:01.000] 作曲 : Jone Pond Ordway
[00:17.360]长亭外 古道边 芳草碧连天
[00:27.929]晚风拂柳笛声残 夕阳山外山
[00:38.524]天之涯 地之角 知交半零落
[00:49.149]一壶浊酒尽余欢 今宵别梦寒
[01:01.125]情千缕 酒一杯 声声离笛催
[01:11.671]问君此去几时还 来时莫徘徊
[01:22.265]天之涯 地之角 知交半零落
[01:32.919]一壶浊酒尽余欢 今宵别梦寒
[02:07.004]天之涯 地之角 知交半零落
[02:17.613]问君此去几时还 来时莫徘徊
[02:28.184]问君此去几时还 来时莫徘徊"""

TS = re.compile(r"^\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$")


def parse(lrc):
    out = []
    for line in (lrc or "").split("\n"):
        m = TS.match(line.strip())
        if not m:
            continue
        body = m.group(4).strip()
        if not body:
            continue
        t = int(m.group(1)) * 60 + int(m.group(2)) + int((m.group(3) or "0").ljust(3, "0")) / 1000.0
        out.append((round(t, 2), body))
    out.sort(key=lambda x: x[0])
    ded = []
    for t, s in out:
        if ded and ded[-1][1] == s:
            continue
        ded.append((t, s))
    return ded


def write_timing(s, pairs, approx=False):
    json.dump({"id": s["id"], "title": s["title"], "dur": s["dur"], "approx": approx,
               "lines": [{"t": t, "s": txt} for t, txt in pairs]},
              open(os.path.join(SYNC, s["id"] + ".timing.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    for s in songs:
        if s["id"] == "送别":
            pairs = parse(SONGBIE_LRC)
            s["lrc"] = SONGBIE_LRC
            s["lyrics"] = [t for _x, t in pairs]
            s["album"] = "送别（电影《厨子戏子痞子》片尾曲）"
            s["netease"] = 1959437612
            s["lyrics_from"] = "netease:1959437612"
            s["nosync"] = False
            write_timing(s, pairs, approx=abs(pairs[-1][0] - s["dur"]) > 8)
            print("送别：%d 行，末行 %.0fs / 录音 %.0fs" % (len(pairs), pairs[-1][0], s["dur"]))
        if s["id"] == "大风吹":
            pairs = parse(s.get("lrc"))
            s["nosync"] = False
            write_timing(s, pairs, approx=abs(pairs[-1][0] - s["dur"]) > 8)
            print("大风吹：%d 行，末行 %.0fs / 录音 %.0fs（尾部器乐）" % (len(pairs), pairs[-1][0], s["dur"]))
    json.dump(songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
