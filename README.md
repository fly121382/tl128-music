# 特零128 的歌

我唱的歌的在线播放站：42 首翻唱，单页播放器 + 播客 RSS。
线上地址 <https://tl128-music.hubingsf.cn/>，仓库 `fly121382/tl128-music`，Pages 走 `docs/`。

## 目录

```
config.json            站点配置（标题、域名、音频源目录）
data/songs.json        曲库：标题 / 原唱 / 专辑 / 时长 / 歌词 / 封面路径
data/covers/*.jpg      专辑封面（抓自 iTunes / Kugou，600×600）
data/sync/*.timing.json 打点/对齐后的歌词时间轴（有就跟歌词一起发给前端）
assets/                样式、播放器脚本、友链图标
tools/tapper.html      歌词打点工具（线上 /tools/tapper.html 也能直接用）
templates/             首页壳 + 单曲分享页
media/                 音频（构建时从 config.source 硬链接进 docs/media，不入库源目录）
docs/                  构建产物（提交到仓库，Pages 直接吃这个目录）
```

## 加一首新歌

1. 把 `歌手 - 歌名.m4a` 放进 `E:\我唱的歌`，用 ffmpeg 写好标签：
   `title=歌名`、`artist=特零128`、`album=我唱的歌`、`comment=原唱：某某 ｜ 翻唱：特零128`
2. `python fetch_meta.py` —— 读标签、搜封面和歌词
   （漏了就跑 `python collect.py` / `python fill_lyrics2.py`，会从 iTunes、Kugou、lrclib 补）
3. `python match_lrc.py --apply` —— 拿本地 `E:\音乐\神之曲1` 里的 .lrc 补时间轴
4. `python make_slugs.py --write` —— 给新歌补 ASCII slug（链接和 OSS 文件名都用它；
   中文自动转拼音，日文/特殊符号在脚本顶部的 `MANUAL` 里手写，也可直接改 `data/songs.json`）
5. `python upload_oss.py` —— 按 `<slug>.m4a` 传到 OSS（已传过的会跳过）
6. `python make_covers.py --upload` —— 封面压成 400×400 / ~25 KB 传到 OSS（GitHub Pages 在国内太慢）
7. `python build.py` —— 生成 `docs/`
8. `python check.py docs` —— 自检（媒体、封面、播客、sitemap）
9. 发布：**只走 git push**

```powershell
git add -A
git commit -m "add: 歌名"
git push
```

不要用 GitHub API 批量改东西（2026-11 那次封号就是 REST 批量写触发的）。
一次 push 一整批，别拆成几十次提交；发完等 Pages 构建（1–2 分钟）再刷新。

## 歌词

- 文本：lrclib / 网易云 / 本地 .lrc，当前 42/42 首都有
- 时间轴：`data/sync/<id>.timing.json`，格式 `{id, title, dur, lines:[{t, s}]}`
  - 来自本地 .lrc 的「同一版伴奏」（时长差 ≤20 秒）自动可用 → 目前 9 首
  - 其余用 `/tools/tapper.html` 打点：放歌 → 空格逐行记时间 → 导出 JSON 丢进 `data/sync/` → 重新 build
- 前端：`songs.json` 里带 `y` 字段的会自动高亮当前行并在歌词框里滚动
- 导到本地：`python export_lyrics.py` —— 按站上的时间轴（含 `data/offsets.json` 的整体偏移）
  给 `E:\我唱的歌` 里每首歌写同名 `.lrc` + `.srt`，可直接丢给播放器/剪辑软件

## 本地预览

```powershell
python build.py --out preview --base http://127.0.0.1:8777
node serve.mjs preview 8777     # 必须用带 Range 的服务，否则进度条拖不动
```

## 技术要点

- 单页应用（hash 路由），播放不中断；每首歌另有 `/song/<slug>.html` 静态分享页（带 OG 标签，打开即跳到播放器对应位置）
- MediaSession：手机锁屏、耳机线控可用
- 收藏 / 最近播放 / 倍速 / 上次听到哪，都存 localStorage
- 播客：`/podcast.xml`，42 集，可直接订阅到小宇宙、Apple Podcasts

## 音频托管（阿里云 OSS）

音频不在仓库里，全在阿里云 OSS：**tl128-music-audio** 桶的 `tl128-music/media/`（公开读、支持 Range、audio/mp4）。
封面也在同一个桶的 `tl128-music/covers/<slug>.jpg`（400×400，平均 25 KB）：GitHub Pages 实测只有 ~25 KB/s，
42 张 600×600 封面要拉半分钟；阿里云上海 0.15 秒。config.json 里的 `mediaBase` 指向桶，
`coverBase` 不写就默认 `<mediaBase>/covers`，写成 `false` 就退回「封面放 GitHub Pages」；构建时封面/音频 URL 直接拼到 OSS，仓库里只有 1 MB 静态文件。

为什么单独一个桶：`hubingsf` 桶 2026-11 被刷了 38 GB 流量后，那边关掉了「允许空 Referer」，
只放行 `*.hubingsf.cn` 的 Referer。浏览器放歌没问题，但播客 App、直接打开音频链接、
部分 iOS Safari 的媒体加载都不带 Referer，会 403。OSS 的 Referer 白名单是桶级的，
没法只给某个前缀开口子，所以音频独立成桶：允许空 Referer，别的站的 Referer 照样挡。

- 传新歌：`python upload_oss.py`（已存在且大小一致会自动跳过）
- 换 bucket/地域：改 `config.json` 的 `mediaBase` 和 `ossBucket`，再 `python build.py`
- 密钥放 `.oss_key.json`（已 gitignore，不要提交）
