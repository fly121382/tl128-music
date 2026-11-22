/* 特零128 的歌 —— 单页播放器
 * 路由：#/   #/song/<id>   #/artists   #/artist/<name>   #/favorites   #/friends
 * 状态存在 localStorage('tl128m')：上次歌曲、进度、收藏、倍速、循环、随机、主题
 */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const KEY = 'tl128m';
  const KG_URL = 'https://static-play.kg.qq.com/node/personal_v2?uid=609999822d2d3e8d31'
    + '&shareUid=609999822d2d3e8d31&pageId=homepage_me';

  const S = {
    songs: [], byId: {}, fav: new Set(), favList: [],
    cur: null, qi: -1, shuffle: false, repeat: 'all', speed: 1,
    q: '', sleepAt: 0, sleepTimer: null, fadeTimer: null,
    pos: {},
  };

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const abs = (p) => {
    if (!p) return p || '';
    if (/^https?:\/\//i.test(p)) return p;
    return p.startsWith('/') ? p : '/' + p;
  };
  const enc = (s) => encodeURIComponent(s);

  /* ---------------------------------------------------------------- storage */
  function load() {
    let d = {};
    try { d = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { d = {}; }
    S.fav = new Set(d.fav || []);
    S.shuffle = !!d.shuffle;
    S.repeat = d.repeat || 'all';
    S.speed = d.speed || 1;
    S.last = d.last || null;
    S.pos = d.pos || {};
    S.off = d.off || {};
    S.nosync = new Set(d.nosync || []);
  }
  let saveTimer = 0;
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(KEY, JSON.stringify({
          fav: [...S.fav], shuffle: S.shuffle, repeat: S.repeat, speed: S.speed,
          last: S.cur ? S.cur.id : S.last, pos: S.pos, off: S.off,
          nosync: [...S.nosync],
        }));
      } catch (e) { /* 忽略配额错误 */ }
    }, 300);
  }
  function rememberPos() {
    if (!S.cur) return;
    const d = audio.duration || S.cur.d || 0;
    if (audio.currentTime > 3 && d && audio.currentTime < d - 5) S.pos[S.cur.id] = audio.currentTime;
    else if (audio.currentTime >= d - 5) delete S.pos[S.cur.id];
  }

  /* ---------------------------------------------------------------- audio */
  const audio = document.createElement('audio');
  audio.preload = 'metadata';
  audio.id = 'audio';
  document.body.appendChild(audio);

  function fmt(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    sec = Math.round(sec);
    return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
  }

  function mediaSession() {
    if (!('mediaSession' in navigator) || !S.cur) return;
    const s = S.cur;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: s.t,
        artist: '原唱 ' + s.a + ' ｜ 翻唱 特零128',
        album: s.al || '我唱的歌',
        artwork: [{ src: abs(s.c), sizes: '600x600', type: 'image/jpeg' }],
      });
      navigator.mediaSession.setActionHandler('play', () => play());
      navigator.mediaSession.setActionHandler('pause', () => pause());
      navigator.mediaSession.setActionHandler('previoustrack', () => step(-1));
      navigator.mediaSession.setActionHandler('nexttrack', () => step(1));
    } catch (e) { /* 老浏览器 */ }
  }

  function setCur(song, autoplay) {
    S.cur = song;
    S.qi = S.songs.findIndex((x) => x.id === song.id);
    audio.src = abs(song.m);
    audio.playbackRate = S.speed;
    $('#p-cover').src = abs(song.c);
    $('#p-cover').alt = song.t;
    const t = $('#p-title');
    t.textContent = song.t;
    t.href = '#/song/' + enc(song.id);
    $('#p-artist').textContent = '原唱 ' + song.a + ' · 翻唱 特零128';
    $('#t-dur').textContent = song.dt;
    const start = S.pos[song.id] || 0;
    if (start > 0) {
      audio.addEventListener('loadedmetadata', () => {
        const d = audio.duration || song.d || 0;
        // 上次听到结尾、或者进度比时长还大 → 直接从头开始，否则一加载就 ended 会跳下一首
        const p = (S.pos[song.id] || 0);
        if (!d || p <= 0 || p >= d - 3) {
          audio.currentTime = 0;
          delete S.pos[song.id];
          return;
        }
        if (Math.abs(audio.currentTime - p) > 2) audio.currentTime = p;
      }, { once: true });
    } else {
      // 没有记忆进度时，确保从头播（避免沿用上一首的位置）
      audio.addEventListener('loadedmetadata', () => { audio.currentTime = 0; }, { once: true });
    }
    document.title = song.t + ' · 特零128 的歌';
    mediaSession();
    syncFav();
    syncNow();
    if (autoplay) play();
    save();
    setTimeout(playerLyric, 60);
  }

  function play() {
    if (!S.cur) {
      const first = S.songs[0];
      if (first) setCur(first, true);
      return;
    }
    audio.play().catch(() => { /* 需要用户手势 */ });
  }
  function pause() { audio.pause(); }
  function toggle() { if (audio.paused) play(); else pause(); }

  function step(d) {
    if (!S.songs.length) return;
    let i = S.qi;
    if (S.shuffle) {
      let n = i;
      while (S.songs.length > 1 && n === i) n = Math.floor(Math.random() * S.songs.length);
      i = n;
    } else {
      i = (i + d + S.songs.length) % S.songs.length;
    }
    setCur(S.songs[i], true);
  }

  audio.addEventListener('timeupdate', () => {
    const d = audio.duration || (S.cur ? S.cur.d : 0) || 1;
    const p = Math.min(100, (audio.currentTime / d) * 100);
    $('#seekfill').style.width = p.toFixed(2) + '%';
    $('#t-cur').textContent = fmt(audio.currentTime);
    if (Math.floor(audio.currentTime) % 5 === 0) rememberPos();
    playerLyric();
    syncLyrics();
  });
  audio.addEventListener('loadedmetadata', () => {
    $('#t-dur').textContent = fmt(audio.duration || (S.cur ? S.cur.d : 0));
    if ('mediaSession' in navigator && navigator.mediaSession.setPositionState && audio.duration) {
      try {
        navigator.mediaSession.setPositionState({
          duration: audio.duration, position: audio.currentTime, playbackRate: audio.playbackRate,
        });
      } catch (e) { /* ignore */ }
    }
  });
  audio.addEventListener('play', () => { $('#btn-play').textContent = '⏸'; $('#btn-play').setAttribute('aria-label', '暂停'); playerLyric(); });
  audio.addEventListener('pause', () => { $('#btn-play').textContent = '▶'; $('#btn-play').setAttribute('aria-label', '播放'); rememberPos(); save(); playerLyric(); });
  audio.addEventListener('ended', () => {
    if (!audio.duration || audio.duration < 1) return;   // 加载失败/未知时长不要乱跳
    if (S.repeat === 'one') { audio.currentTime = 0; audio.play(); return; }
    if (!S.shuffle && S.repeat === 'off' && S.qi >= S.songs.length - 1) return;
    step(1);
  });

  /* ---------------------------------------------------------------- 播放器 UI */
  function syncFav() {
    const on = S.cur && S.fav.has(S.cur.id);
    const b = $('#btn-fav');
    b.textContent = on ? '♥' : '♡';
    b.classList.toggle('on', !!on);
    $$('[data-fav]').forEach((el) => {
      const id = el.getAttribute('data-fav');
      const has = S.fav.has(id);
      el.textContent = has ? '♥' : '♡';
      el.classList.toggle('on', has);
    });
  }
  function syncNow() {
    $$('.song[data-id]').forEach((el) => {
      el.classList.toggle('cur', !!S.cur && el.getAttribute('data-id') === S.cur.id);
    });
    $$('.dw-item').forEach((el) => {
      el.classList.toggle('cur', !!S.cur && el.getAttribute('data-id') === S.cur.id);
    });
    $('#btn-shuffle').classList.toggle('on', S.shuffle);
    $('#btn-repeat').classList.toggle('on', S.repeat !== 'off');
    $('#btn-repeat').textContent = S.repeat === 'one' ? '↻¹' : '↻';
    $('#btn-repeat').title = '循环：' + ({ off: '关', all: '列表循环', one: '单曲循环' }[S.repeat]);
    $('#btn-speed').textContent = S.speed.toFixed(1) + '×';
  }

  function toggleFav(id) {
    id = id || (S.cur && S.cur.id);
    if (!id) return;
    if (S.fav.has(id)) { S.fav.delete(id); toast('已取消收藏'); }
    else { S.fav.add(id); toast('已收藏'); }
    save();
    syncFav();
    if (location.hash.startsWith('#/favorites')) render();
  }

  let toastEl = null;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add('on');
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => toastEl.classList.remove('on'), 1600);
  }

  /* 进度条：点击/拖动 */
  (() => {
    const bar = $('#seekbar');
    let dragging = false;
    const seekTo = (ev) => {
      const r = bar.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
      const d = audio.duration || (S.cur ? S.cur.d : 0) || 0;
      if (d) {
        audio.currentTime = p * d;
        $('#seekfill').style.width = (p * 100).toFixed(2) + '%';
        $('#t-cur').textContent = fmt(audio.currentTime);
      }
    };
    bar.addEventListener('pointerdown', (ev) => {
      dragging = true; bar.classList.add('drag');
      seekTo(ev);
      try { bar.setPointerCapture(ev.pointerId); } catch (e) { /* 某些合成事件没有 pointerId */ }
    });
    bar.addEventListener('pointermove', (ev) => { if (dragging) seekTo(ev); });
    bar.addEventListener('pointerup', () => { dragging = false; bar.classList.remove('drag'); });
    bar.addEventListener('pointercancel', () => { dragging = false; bar.classList.remove('drag'); });
    bar.addEventListener('keydown', (ev) => {
      if (ev.key === 'ArrowRight') { audio.currentTime += 5; ev.preventDefault(); }
      if (ev.key === 'ArrowLeft') { audio.currentTime -= 5; ev.preventDefault(); }
    });
  })();

  /* 睡眠定时 */
  function setSleep(min) {
    clearTimeout(S.sleepTimer);
    clearTimeout(S.fadeTimer);
    audio.volume = Math.min(1, Number($('#vol').value || 100) / 100);
    if (!min) {
      S.sleepAt = 0;
      $('#btn-sleep').classList.remove('on');
      toast('睡眠定时已关闭');
      return;
    }
    S.sleepAt = Date.now() + min * 60000;
    $('#btn-sleep').classList.add('on');
    toast('将在 ' + min + ' 分钟后停止播放');
    const run = () => {
      const left = S.sleepAt - Date.now();
      if (left <= 0) {
        fadeOut(20);
        S.sleepAt = 0;
        $('#btn-sleep').classList.remove('on');
        return;
      }
      if (left <= 20000) fadeOut(left / 1000);
      S.sleepTimer = setTimeout(run, 1000);
    };
    S.sleepTimer = setTimeout(run, 1000);
  }
  function fadeOut(seconds) {
    const from = audio.volume;
    const steps = Math.max(1, Math.round(seconds * 4));
    let i = 0;
    clearInterval(S.fadeTimer);
    S.fadeTimer = setInterval(() => {
      i += 1;
      audio.volume = Math.max(0, from * (1 - i / steps));
      if (i >= steps) {
        clearInterval(S.fadeTimer);
        audio.pause();
        audio.volume = from;
      }
    }, 250);
  }

  /* 播放器标题跟着歌词走 */
  function playerLyric() {
    const el = $('#p-title');
    if (!S.cur || !el) return;
    if (!Array.isArray(S.cur.y) || audio.paused || S.nosync.has(S.cur.id)) {
      el.textContent = S.cur.t;
      el.classList.remove('singing');
      el.title = '';
      return;
    }
    const t = audio.currentTime + 0.15 + (S.cur.o || 0) + (S.off[S.cur.id] || 0);
    const arr = S.cur.y;
    let k = -1;
    for (let i = 0; i < arr.length; i++) { if (arr[i][0] <= t) k = i; else break; }
    if (k < 0) {
      el.textContent = S.cur.t;
      el.classList.remove('singing');
      return;
    }
    const txt = (S.cur.l && S.cur.l.length === arr.length && S.cur.l[k]) || arr[k][1];
    el.textContent = txt;
    el.classList.add('singing');
    el.title = S.cur.t + ' · 特零128';
  }

  /* 同步歌词：只有这首歌已经有打点数据（s.y）才生效 */
  function syncLyrics() {
    const box = document.querySelector('.lyrics[data-sync]');
    if (!box || !S.cur || !Array.isArray(S.cur.y)) return;
    const arr = S.cur.y;
    const t = audio.currentTime + 0.15 + (S.cur.o || 0) + (S.off[S.cur.id] || 0);
    let k = -1;
    for (let i = 0; i < arr.length; i++) {
      if (arr[i][0] <= t) k = i; else break;
    }
    if (k === box._k) return;
    box._k = k;
    const nodes = box.querySelectorAll('.lrc-line');
    nodes.forEach((n, i) => n.classList.toggle('on', i === k));
    const on = nodes[k];
    if (on) {
      const rb = box.getBoundingClientRect();
      const rl = on.getBoundingClientRect();
      const rel = rl.top - rb.top;
      if (rel < 44 || rel > rb.height - 90) {
        box.scrollTo({ top: box.scrollTop + rel - rb.height / 2 + rl.height / 2, behavior: 'smooth' });
      }
    }
  }

  /* 播放列表抽屉 */
  function openDrawer(on) {
    $('#drawer').classList.toggle('open', on);
    $('#mask').classList.toggle('on', on);
    $('#drawer').setAttribute('aria-hidden', on ? 'false' : 'true');
    if (on) renderDrawer();
  }
  function renderDrawer() {
    const q = ($('#dw-q').value || '').trim().toLowerCase();
    const list = S.songs.filter((s) => !q || (s.t + ' ' + s.a).toLowerCase().includes(q));
    $('#dw-count').textContent = S.songs.length + ' 首';
    $('#dw-list').innerHTML = list.map((s) => `
      <li class="dw-item${S.cur && S.cur.id === s.id ? ' cur' : ''}" data-id="${esc(s.id)}">
        <img src="${abs(s.c)}" alt="" loading="lazy">
        <span class="w"><span class="t">${esc(s.t)}</span><span class="a">原唱 ${esc(s.a)}</span></span>
        <span class="d">${s.dt}</span>
      </li>`).join('') || '<li class="loading">没有匹配的歌</li>';
  }

  /* ---------------------------------------------------------------- 视图 */
  function rowHTML(s, i) {
    const on = S.cur && S.cur.id === s.id;
    const fav = S.fav.has(s.id);
    return `<li class="song${on ? ' cur' : ''}" data-id="${esc(s.id)}">
      <span class="s-idx"><span class="num">${i + 1}</span><span class="eq">♪</span></span>
      <img class="s-cover" src="${abs(s.c)}" alt="" loading="lazy" width="44" height="44">
      <span class="s-main">
        <a class="s-title" href="#/song/${enc(s.id)}">${s.star ? '<span class="s-star" title="特零推荐">★</span>' : ''}${esc(s.t)}</a>
        <span class="s-artist">原唱 · ${esc(s.a)}${s.al ? ' · 《' + esc(s.al) + '》' : ''}</span>
      </span>
      <span class="s-dur">${s.dt}</span>
      <button class="s-fav${fav ? ' on' : ''}" data-fav="${esc(s.id)}" type="button" aria-label="收藏">${fav ? '♥' : '♡'}</button>
    </li>`;
  }

  function applyFilter() {
    const q = S.q.trim().toLowerCase();
    return !q ? S.songs : S.songs.filter((s) => (s.t + ' ' + s.a + ' ' + (s.al || '')).toLowerCase().includes(q));
  }

  function viewHome() {
    const list = applyFilter();
    const totalMin = Math.round(S.songs.reduce((a, s) => a + s.d, 0) / 60);
    const starred = S.songs.filter((s) => s.star);
    $('#view').innerHTML = `
      <section class="hero">
        <h1>我唱的歌</h1>
        <p>${S.songs.length} 首翻唱 · 约 ${totalMin} 分钟 · 全部由 特零128 演唱${starred.length ? ' · 带 ★ 的是我自己推荐的' : ''}</p>
        <div class="hero-btns">
          <button class="btn primary" data-act="playall" type="button">全部播放</button>
          <button class="btn" data-act="lucky" type="button">手气不错</button>
          <a class="btn" href="#/artists">根据原唱</a>
          <a class="btn" href="${KG_URL}" target="_blank" rel="noopener">全民K歌主页 ↗</a>
          ${S.last ? '<button class="btn" data-act="resume" type="button">继续上次</button>' : ''}
        </div>
        <p class="hero-note">★ 是我自己觉得唱得还行的；每首都标了原唱和原专辑。</p>
      </section>
      ${S.q ? '' : ''}
      <section class="block">
        <h2 class="block-title"><b>${S.q ? '搜索' : '全部'}</b><span>${list.length} 首${S.q ? ' · 「' + esc(S.q) + '」' : ''}</span></h2>
        <ol class="songs">${list.map(rowHTML).join('') || '<li class="loading">没有找到，换个词试试。</li>'}</ol>
      </section>`;
    syncNow();
  }

  function viewSong(id) {
    const s = S.byId[id];
    if (!s) { $('#view').innerHTML = '<p class="loading">没有这首歌。</p>'; return; }
    const rel = S.songs.filter((x) => x.a === s.a && x.id !== s.id);
    const fav = S.fav.has(s.id);
    const credit = s.l.filter((l) => /^(作词|作曲|编曲|演唱|原唱|制作人|混音|母带|翻唱|词|曲)/.test(l));
    const tr = Array.isArray(s.tr) ? s.tr : null;
    const synced = Array.isArray(s.y) && s.y.length > 1 && !S.nosync.has(s.id);
    const canSync = Array.isArray(s.y) && s.y.length > 1;
    let lyricHTML = '<span class="lyrics-empty">这首暂时没有抓到歌词。</span>';
    if (s.l.length) {
      lyricHTML = s.l.map((l, i) => {
        const isCredit = credit.includes(l);
        const sub = tr && tr[i] && tr[i].trim()
          ? `<span class="lrc-tr">${esc(tr[i])}</span>` : '';
        return `<span class="lrc-line${isCredit ? ' lrc-credit' : ''}">${esc(l)}${sub}</span>`;
      }).join('');
    }
    $('#view').innerHTML = `
      <div class="song-view">
        <div class="sv-head">
          <img class="sv-cover" src="${abs(s.c)}" alt="${esc(s.t)} 封面">
          <div class="sv-info">
            <p class="sv-kicker">${esc(s.al || '翻唱作品')}</p>
            <h1 class="sv-title">${esc(s.t)}</h1>
            <p class="sv-by">原唱 <b>${esc(s.a)}</b> ｜ 翻唱 <b>特零128</b></p>
            <div class="sv-meta">
              <span class="chip">${s.dt}</span>
              <span class="chip">${s.kb} kbps</span>
              <span class="chip">${(s.sz / 1048576).toFixed(1)} MB</span>
              <span class="chip">${s.l.length ? '有歌词' : '暂无歌词'}</span>
            </div>
            <div class="sv-acts">
              <button class="btn primary" data-act="playone" data-id="${esc(s.id)}" type="button">${S.cur && S.cur.id === s.id && !audio.paused ? '正在播放' : '播放'}</button>
              <button class="btn" data-act="fav" data-id="${esc(s.id)}" type="button">${fav ? '♥ 已收藏' : '♡ 收藏'}</button>
              <button class="btn" data-act="share" data-id="${esc(s.id)}" type="button">分享链接</button>
              <a class="btn" href="/song/${enc(s.id)}.html">单曲页</a>
            </div>
          </div>
        </div>
        <div class="lyrics"${synced ? ' data-sync="1"' : ''}>
          <h2>歌词${synced ? ' · 同步' : ''}
            ${synced ? `<span class="lrc-nudge">
              <button data-nudge="-2" type="button">−2s</button>
              <button data-nudge="-0.5" type="button">−0.5s</button>
              <button data-nudge="0.5" type="button">+0.5s</button>
              <button data-nudge="2" type="button">+2s</button>
              <button data-nosync="1" type="button">关同步</button></span>` : ''}
          </h2>
          ${synced && s.ya ? '<p class="lrc-hint">时间轴取自原曲，可能有整体偏移 —— 用上面的 −/+ 调，调到对为止（每首单独记）。</p>' : ''}
          ${!synced && canSync ? '<p class="lrc-hint">这首歌的同步被你关掉了。<button data-nosync-off="1" type="button" class="linkbtn">开同步</button></p>' : ''}
          ${lyricHTML}
        </div>
        ${rel.length ? `<section class="block"><h2 class="block-title"><b>同一原唱</b><span>${esc(s.a)} · ${rel.length} 首</span></h2>
          <ol class="rel-list">${rel.map((x) => `<li data-id="${esc(x.id)}">
            <img src="${abs(x.c)}" alt="" loading="lazy">
            <a class="t" href="#/song/${enc(x.id)}">${esc(x.t)}</a><span class="d">${x.dt}</span></li>`).join('')}</ol>
        </section>` : ''}
      </div>`;
    syncNow();
  }

  function viewArtists() {
    const map = new Map();
    S.songs.forEach((s) => {
      if (!map.has(s.a)) map.set(s.a, []);
      map.get(s.a).push(s);
    });
    const arr = [...map.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0], 'zh'));
    $('#view').innerHTML = `
      <section class="hero"><h1>根据原唱</h1><p>${arr.length} 位原唱歌手 · ${S.songs.length} 首 · <a href="#/">← 回到全部</a></p></section>
      <div class="artist-grid">
        ${arr.map(([name, list]) => `<a class="artist-card" href="#/artist/${enc(name)}">
          <img src="${abs(list[0].c)}" alt="" loading="lazy">
          <span><span class="n">${esc(name)}</span><br><span class="c">${list.length} 首</span></span>
        </a>`).join('')}
      </div>`;
  }

  function viewArtist(name) {
    const list = S.songs.filter((s) => s.a === name);
    $('#view').innerHTML = `
      <section class="hero"><h1>${esc(name)}</h1><p>特零128 翻唱了 ${list.length} 首 · <a href="#/artists">全部原唱 →</a></p>
      <div class="hero-btns"><button class="btn primary" data-act="playartist" data-a="${esc(name)}" type="button">播放这 ${list.length} 首</button></div></section>
      <ol class="songs">${list.map(rowHTML).join('')}</ol>`;
    syncNow();
  }

  function viewFavorites() {
    const list = S.songs.filter((s) => S.fav.has(s.id));
    $('#view').innerHTML = `
      <section class="hero"><h1>我的收藏</h1><p>${list.length} 首 · 存在这台设备的浏览器里</p>
      ${list.length ? '<div class="hero-btns"><button class="btn primary" data-act="playfavs" type="button">播放收藏</button></div>' : ''}</section>
      ${list.length ? `<ol class="songs">${list.map(rowHTML).join('')}</ol>`
        : '<p class="loading">还没有收藏。点歌单或播放器上的 ♡ 就能加进来。</p>'}`;
    syncNow();
  }

  function viewFriends() {
    $('#view').innerHTML = `
      <section class="hero"><h1>友链</h1><p>同路的站点</p></section>
      <ul class="friends">
        <li><a class="friend" href="https://timeleaper128.hubingsf.cn/" target="_blank" rel="noopener">
          <img src="/assets/friends/tl128.png" alt="特零128小站 图标">
          <span class="fw"><span class="fn">特零128小站</span>
          <span class="fd">小说、诗与杂文：一个半桶水的科幻 / 百合 / 架空世界写手。</span>
          <span class="fh">timeleaper128.hubingsf.cn</span></span>
          <span class="go">↗</span></a></li>
      </ul>`;
  }

  function viewNetease() {
    $('#view').innerHTML = '<p class="loading">正在读歌单…</p>';
    fetch('/assets/netease.json', { cache: 'no-cache' })
      .then((r) => r.json())
      .then((d) => {
        const own = d.playlists.filter((p) => p.own);
        const sub = d.playlists.filter((p) => !p.own);
        const card = (p) => `<a class="nc-card" href="${p.url}" target="_blank" rel="noopener">
          <img src="${esc(p.cover)}?param=240y240" alt="" loading="lazy">
          <span class="nc-body">
            <span class="nc-name">${esc(p.name)}</span>
            <span class="nc-meta">${p.count} 首${p.play ? ' · ' + (p.play > 9999 ? (p.play / 10000).toFixed(1) + ' 万' : p.play) + ' 次播放' : ''}</span>
            ${p.tracks && p.tracks.length ? `<span class="nc-tr">${p.tracks.slice(0, 3).map((t) => esc(t.n)).join(' · ')}…</span>` : ''}
          </span>
        </a>`;
        $('#view').innerHTML = `
          <section class="hero">
            <h1>我的网易云</h1>
            <p>${own.length} 个自建歌单 · ${sub.length} 个收藏歌单 · 数据更新于 ${esc(d.updated)}</p>
            <div class="hero-btns">
              <a class="btn primary" href="https://music.163.com/user?id=${d.uid}" target="_blank" rel="noopener">去网易云看主页 ↗</a>
            </div>
          </section>
          <section class="block"><h2 class="block-title"><b>自建歌单</b><span>${own.length} 个</span></h2>
            <div class="nc-grid">${own.map(card).join('')}</div></section>
          <details class="block nc-fold">
            <summary><b>收藏歌单</b><span>${sub.length} 个 · 点开看</span></summary>
            <div class="nc-grid">${sub.map(card).join('')}</div>
          </details>
          <p class="nc-note">歌单是快照，想听最新的直接点进网易云。这边只做推荐，不内嵌播放。</p>`;
        mark('netease');
      })
      .catch(() => {
        $('#view').innerHTML = '<p class="loading">歌单数据读不到，稍后再试。</p>';
      });
  }

  function route() {
    const h = decodeURIComponent(location.hash.replace(/^#/, '') || '/');
    const parts = h.split('/').filter(Boolean);
    $$('#nav a[data-nav]').forEach((a) => a.classList.remove('on'));
    if (parts[0] === 'song') { viewSong(parts[1]); return; }
    if (parts[0] === 'artists') { viewArtists(); return; }
    if (parts[0] === 'artist') { viewArtist(parts.slice(1).join('/')); return; }
    if (parts[0] === 'favorites') { viewFavorites(); mark('favorites'); return; }
    if (parts[0] === 'netease') { viewNetease(); return; }
    if (parts[0] === 'friends') { viewFriends(); mark('friends'); return; }
    viewHome(); mark('home');
  }
  function mark(n) { const a = $('#nav a[data-nav="' + n + '"]'); if (a) a.classList.add('on'); }

  /* ---------------------------------------------------------------- 事件 */
  function bind() {
    $('#btn-play').onclick = toggle;
    $('#btn-next').onclick = () => step(1);
    $('#btn-prev').onclick = () => (audio.currentTime > 4 ? (audio.currentTime = 0) : step(-1));
    $('#btn-shuffle').onclick = () => { S.shuffle = !S.shuffle; save(); syncNow(); toast(S.shuffle ? '随机播放：开' : '随机播放：关'); };
    $('#btn-repeat').onclick = () => {
      S.repeat = { off: 'all', all: 'one', one: 'off' }[S.repeat];
      save(); syncNow();
      toast({ off: '循环：关', all: '列表循环', one: '单曲循环' }[S.repeat]);
    };
    $('#btn-fav').onclick = () => toggleFav();
    $('#btn-speed').onclick = () => {
      const opts = [1, 1.25, 1.5, 0.75];
      S.speed = opts[(opts.indexOf(S.speed) + 1) % opts.length];
      audio.playbackRate = S.speed;
      save(); syncNow();
      toast('倍速 ' + S.speed.toFixed(2).replace(/0$/, '') + '×');
    };
    $('#btn-queue').onclick = () => openDrawer(true);
    $('#dw-close').onclick = () => openDrawer(false);
    $('#mask').onclick = () => openDrawer(false);
    $('#dw-q').oninput = renderDrawer;
    $('#vol').oninput = (e) => { audio.volume = Number(e.target.value) / 100; };
    audio.volume = 1;

    $('#btn-sleep').onclick = (e) => {
      const pop = $('#sleep-pop');
      const on = pop.classList.toggle('on');
      if (on) {
        const r = e.currentTarget.getBoundingClientRect();
        pop.style.left = Math.min(window.innerWidth - 170, Math.max(8, r.left - 40)) + 'px';
        pop.style.bottom = (window.innerHeight - r.top + 8) + 'px';
      }
    };
    $$('#sleep-pop button').forEach((b) => {
      b.onclick = () => { setSleep(Number(b.dataset.min)); $('#sleep-pop').classList.remove('on'); };
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#sleep-pop') && !e.target.closest('#btn-sleep')) {
        $('#sleep-pop').classList.remove('on');
      }
    });

    $('#theme').onclick = () => {
      const cur = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = cur;
      try { localStorage.setItem('tl128m-theme', cur); } catch (e) { /* ignore */ }
    };
    if (!document.documentElement.dataset.theme && window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches) {
      document.documentElement.dataset.theme = 'dark';
    }

    let qi = 0;
    $('#q').oninput = (e) => {
      S.q = e.target.value;
      clearTimeout(qi);
      qi = setTimeout(() => {
        if (!/^#\/($|\?)/.test(location.hash) && location.hash !== '' && location.hash !== '#/') {
          location.hash = '#/';
        } else {
          viewHome();
        }
      }, 140);
    };

    /* 视图里的事件委托 */
    $('#view').addEventListener('click', (e) => {
      const nd = e.target.closest('[data-nudge]');
      if (nd && S.cur) {
        const d = Number(nd.dataset.nudge);
        S.off[S.cur.id] = Math.round(((S.off[S.cur.id] || 0) + d) * 10) / 10;
        save();
        const box = document.querySelector('.lyrics');
        if (box) box._k = undefined;
        syncLyrics();
        toast('歌词偏移 ' + (S.off[S.cur.id] > 0 ? '+' : '') + S.off[S.cur.id].toFixed(1) + ' 秒');
        return;
      }
      if (e.target.closest('[data-nosync]') && S.cur) {
        S.nosync.add(S.cur.id);
        save();
        route();
        toast('这首歌的同步已关掉（再点「开同步」能恢复）');
        return;
      }
      if (e.target.closest('[data-nosync-off]') && S.cur) {
        S.nosync.delete(S.cur.id);
        save();
        route();
        toast('已恢复同步');
        return;
      }
      const fav = e.target.closest('[data-fav]');
      if (fav) { e.preventDefault(); toggleFav(fav.getAttribute('data-fav')); return; }
      const act = e.target.closest('[data-act]');
      if (act) {
        const a = act.dataset.act;
        if (a === 'playall') { if (S.songs[0]) setCur(S.songs[0], true); }
        if (a === 'lucky') { setCur(S.songs[Math.floor(Math.random() * S.songs.length)], true); }
        if (a === 'resume' && S.last && S.byId[S.last]) setCur(S.byId[S.last], true);
        if (a === 'playone') setCur(S.byId[act.dataset.id], true);
        if (a === 'fav') toggleFav(act.dataset.id);
        if (a === 'playfavs') { const l = S.songs.filter((x) => S.fav.has(x.id)); if (l[0]) setCur(l[0], true); }
        if (a === 'playartist') { const l = S.songs.filter((x) => x.a === act.dataset.a); if (l[0]) setCur(l[0], true); }
        if (a === 'share') {
          const s = S.byId[act.dataset.id];
          const u = location.origin + '/song/' + enc(s.id) + '.html';
          if (navigator.clipboard) navigator.clipboard.writeText(u).then(() => toast('链接已复制'), () => toast('复制失败'));
          else toast(u);
        }
        return;
      }
      const row = e.target.closest('.song[data-id], .rel-list li[data-id]');
      if (row && !e.target.closest('a')) {
        const s = S.byId[row.getAttribute('data-id')];
        if (s) { if (S.cur && S.cur.id === s.id) toggle(); else setCur(s, true); }
      }
    });

    $('#dw-list').addEventListener('click', (e) => {
      const it = e.target.closest('.dw-item');
      if (!it) return;
      const s = S.byId[it.getAttribute('data-id')];
      if (s) { setCur(s, true); openDrawer(false); }
    });

    document.addEventListener('keydown', (e) => {
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) {
        if (e.key === 'Escape') t.blur();
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case ' ': e.preventDefault(); toggle(); break;
        case 'ArrowRight': e.preventDefault(); audio.currentTime += 5; break;
        case 'ArrowLeft': e.preventDefault(); audio.currentTime -= 5; break;
        case 'ArrowUp': e.preventDefault(); audio.volume = Math.min(1, audio.volume + .1); $('#vol').value = audio.volume * 100; break;
        case 'ArrowDown': e.preventDefault(); audio.volume = Math.max(0, audio.volume - .1); $('#vol').value = audio.volume * 100; break;
        case 'm': audio.muted = !audio.muted; toast(audio.muted ? '静音' : '取消静音'); break;
        case 'f': toggleFav(); break;
        case 'q': openDrawer(!$('#drawer').classList.contains('open')); break;
        case 's': $('#btn-shuffle').click(); break;
        case 'r': $('#btn-repeat').click(); break;
        case '/': e.preventDefault(); $('#q').focus(); break;
        default: break;
      }
    });

    window.addEventListener('hashchange', route);
    window.addEventListener('beforeunload', rememberPos);

    if ('mediaSession' in navigator) {
      navigator.mediaSession.setActionHandler('seekbackward', () => { audio.currentTime -= 10; });
      navigator.mediaSession.setActionHandler('seekforward', () => { audio.currentTime += 10; });
    }
  }

  /* ---------------------------------------------------------------- 启动 */
  async function boot() {
    load();
    try {
      const r = await fetch('/assets/songs.json', { cache: 'no-cache' });
      S.songs = await r.json();
    } catch (e) {
      $('#view').innerHTML = '<p class="loading">曲库载入失败，刷新试试。</p>';
      return;
    }
    S.songs.forEach((s) => { S.byId[s.id] = s; });
    bind();
    route();
    if (S.last && S.byId[S.last]) {
      const s = S.byId[S.last];
      const pos = S.pos[s.id] || 0;
      S.cur = s;
      S.qi = S.songs.findIndex((x) => x.id === s.id);
      audio.src = abs(s.m);
      $('#p-cover').src = abs(s.c);
      $('#p-cover').alt = s.t;
      $('#p-title').textContent = s.t;
      $('#p-title').href = '#/song/' + enc(s.id);
      $('#p-artist').textContent = '原唱 ' + s.a + ' · 翻唱 特零128';
      $('#t-dur').textContent = s.dt;
      $('#t-cur').textContent = fmt(pos);
      $('#seekfill').style.width = (pos / (s.d || 1) * 100).toFixed(2) + '%';
      $('#btn-speed').textContent = S.speed.toFixed(1) + '×';
      syncFav();
      mediaSession();
      audio.addEventListener('loadedmetadata', () => {
        const d = audio.duration || s.d || 0;
        if (pos && d && pos < d - 3) audio.currentTime = pos;
        else { audio.currentTime = 0; delete S.pos[s.id]; }
      }, { once: true });
    }
    syncNow();
  }

  boot();
})();
