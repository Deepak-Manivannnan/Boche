/* Boche — reveal.js
   The results reveal on the Lucky Draw screen. It only shows winners the server has already published;
   nothing here picks, orders by chance or changes a winner. The "matrix" digits are decoration that settle
   on each published lucky number one character at a time. */
(function (root) {
  'use strict';

  var CHARS = '0123456789ABCDEFGHJKLMNPRSTUVWXYZ';

  /* Reveal order and the signed-in member's personal ending. Pure: same input, same plan. */
  function plan(winners, myNumbers) {
    var mine = {}; (myNumbers || []).forEach(function (n) { mine[n] = 1; });
    var order = (winners || []).slice().sort(function (a, b) { return b.rank - a.rank; }).map(function (w) {
      return { rank: w.rank, label: w.label, amount: w.amount, ticket: w.ticket, name: w.name, mine: !!mine[w.ticket], big: w.rank <= 3 };
    });
    var won = order.filter(function (w) { return w.mine; }).sort(function (a, b) { return a.rank - b.rank; });
    return {
      order: order,
      outcome: {
        won: won.length > 0,
        amount: won.reduce(function (t, w) { return t + w.amount; }, 0),
        best: won.length ? won[0].label : null,
        entered: (myNumbers || []).length > 0
      }
    };
  }

  /* One frame of the digit roll: the first `locked` characters are final, the rest flicker. Spaces stay. */
  function scrambleFrame(target, locked, seed) {
    var x = Math.floor((seed || 0.5) * 2147483647) || 1, out = '';
    for (var i = 0; i < target.length; i++) {
      x = (x * 48271) % 2147483647;
      out += i < locked || target[i] === ' ' ? target[i] : CHARS[x % CHARS.length];
    }
    return out;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function inr(n) { return '₹' + Number(n).toLocaleString('en-IN'); }
  function ordinal(n) { return n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[n] || 'th'); }

  /* Falling 0/1 columns: shown only while a number is rolling. */
  function matrix() {
    var cols = '';
    for (var i = 0; i < 16; i++) {
      var s = ''; for (var k = 0; k < 28; k++) s += Math.random() < 0.5 ? '0' : '1';
      cols += '<i style="left:' + (i * 6.4 + 1) + '%;animation-duration:' + (3 + Math.random() * 4).toFixed(1) + 's;animation-delay:-' + (Math.random() * 6).toFixed(1) + 's">' + s + '</i>';
    }
    return '<div class="rv-matrix" aria-hidden="true">' + cols + '</div>';
  }
  function sparkles() {
    var h = '';
    for (var i = 0; i < 22; i++) h += '<i style="left:' + (Math.random() * 100).toFixed(1) + '%;top:' + (Math.random() * 100).toFixed(1) + '%;animation-delay:-' + (Math.random() * 4).toFixed(1) + 's;animation-duration:' + (2.5 + Math.random() * 3).toFixed(1) + 's"></i>';
    return '<div class="rv-sparkle" aria-hidden="true">' + h + '</div>';
  }
  function balloons() {
    var cols = ['#D9B45A', '#B3261E', '#2F7A4C', '#F5E2A8', '#C9A04A', '#8C6420'], h = '';
    for (var i = 0; i < 9; i++) h += '<i style="left:' + (6 + i * 10.5) + '%;background:' + cols[i % cols.length] + ';animation-delay:' + (i * 0.12).toFixed(2) + 's;animation-duration:' + (2.6 + (i % 3) * 0.5).toFixed(1) + 's"></i>';
    return '<div class="rv-balloons" aria-hidden="true">' + h + '</div>';
  }
  /* Sounds. Lucky 7: synthesised bells with a generated hall reverb, and a rising flourish once all seven are in.
     Top three: recorded public-domain clips in /sfx (drum roll under the spin, cymbal crash on the lock, a brass
     fanfare, applause; a longer fanfare and cheering for 1st). Clips are fetched once and decoded on first use;
     if one is missing the synth fanfare plays instead. Muting is remembered. */
  var sfx = (function () {
    var ctx = null, on = true, verb = null, bus = null, bufs = {}, loading = {}, live = [];
    try { on = root.localStorage.getItem('bocheclub-rv-sound') !== 'off'; } catch (e) { on = true; }
    function ac() {
      if (!on) return null;
      if (!ctx) {
        var C = root.AudioContext || root.webkitAudioContext; if (!C) return null;
        try { ctx = new C(); } catch (e) { return null; }
        bus = ctx.createGain(); bus.gain.value = 0.9; bus.connect(ctx.destination);
        try {
          var len = ctx.sampleRate * 2.6, ir = ctx.createBuffer(2, len, ctx.sampleRate);
          for (var ch = 0; ch < 2; ch++) { var d = ir.getChannelData(ch); for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3); }
          verb = ctx.createConvolver(); verb.buffer = ir;
          var wet = ctx.createGain(); wet.gain.value = 0.32; verb.connect(wet); wet.connect(bus);
        } catch (e) { verb = null; }
      }
      if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
      return ctx;
    }
    function out(node) { node.connect(bus); if (verb) node.connect(verb); }
    function tone(f, t0, dur, type, vol) {
      var c = ac(); if (!c) return;
      var o = c.createOscillator(), g = c.createGain(), t = c.currentTime + t0;
      o.type = type || 'sine'; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol || 0.15, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); out(g); o.start(t); o.stop(t + dur + 0.05);
    }
    /* A bell: fundamental plus inharmonic partials that die away faster. */
    function bell(f, t0, vol) {
      tone(f, t0, 1.6, 'sine', vol); tone(f * 2.01, t0, 0.9, 'sine', vol * 0.35);
      tone(f * 2.76, t0, 0.6, 'sine', vol * 0.18); tone(f * 5.4, t0, 0.25, 'sine', vol * 0.08);
    }
    function load(name) {
      var c = ac(); if (!c || bufs[name] || loading[name] || !root.fetch) return;
      loading[name] = true;
      root.fetch('/sfx/' + name + '.mp3').then(function (r) { if (!r.ok) throw 0; return r.arrayBuffer(); })
        .then(function (a) { return new Promise(function (ok, no) { c.decodeAudioData(a, ok, no); }); })
        .then(function (b) { bufs[name] = b; }, function () { loading[name] = false; });
    }
    /* Plays a clip; returns false if it is not loaded yet. fadeIn ramps it up (used for the drum roll). */
    function clip(name, vol, fadeIn) {
      var c = ac(); if (!c || !bufs[name]) return false;
      var s = c.createBufferSource(), g = c.createGain(), t = c.currentTime;
      s.buffer = bufs[name];
      if (fadeIn) { g.gain.setValueAtTime(vol * 0.25, t); g.gain.linearRampToValueAtTime(vol, t + fadeIn); } else g.gain.value = vol;
      s.connect(g); g.connect(bus); s.start(t);
      var item = { s: s, g: g }; live.push(item);
      s.onended = function () { live = live.filter(function (x) { return x !== item; }); };
      return item;
    }
    function fade(item, sec) {
      if (!item || !ctx) return;
      var t = ctx.currentTime; item.g.gain.cancelScheduledValues(t); item.g.gain.setValueAtTime(item.g.gain.value, t);
      item.g.gain.linearRampToValueAtTime(0.0001, t + sec); try { item.s.stop(t + sec + 0.05); } catch (e) {}
    }
    function synthFanfare(grand) {
      var run = grand ? [392, 523, 659, 784, 1047] : [523, 659, 784];
      run.forEach(function (f, i) { tone(f, i * 0.11, 0.5, 'sawtooth', 0.05); tone(f, i * 0.11, 0.5, 'triangle', 0.12); });
      var at = run.length * 0.11, hold = grand ? 2.2 : 1.3;
      [523, 659, 784, 1047].concat(grand ? [1319] : []).forEach(function (f) { tone(f, at, hold, 'triangle', 0.1); tone(f, at, hold, 'sawtooth', 0.025); });
      tone(131, at, hold, 'sine', 0.18);
    }
    var drum = null, run = 0;
    return {
      isOn: function () { return on; },
      toggle: function () { on = !on; try { root.localStorage.setItem('bocheclub-rv-sound', on ? 'on' : 'off'); } catch (e) {} if (!on) this.stop(); return on; },
      /* Start fetching the clips early (called when the reveal opens), so they are ready by the top three. */
      preload: function () { ['roll', 'crash', 'fanfare', 'fanfare-grand', 'applause', 'cheer'].forEach(load); },
      ding: function (k) { bell([784, 880, 988, 1047, 1175, 1319, 1568][k % 7], 0, 0.14); },
      /* Seven stubs filled: a quick rising arpeggio and a shimmer. */
      flourish: function () {
        [523, 659, 784, 1047, 1319].forEach(function (f, i) { bell(f, i * 0.09, 0.09); });
        for (var k = 0; k < 8; k++) tone(2093 + Math.random() * 1500, 0.5 + k * 0.07, 0.3, 'sine', 0.03);
      },
      /* Drum roll under a top-three spin; falls back to synth ticks per locked character if not loaded. */
      rollStart: function () { this.rollStop(0); drum = clip('roll', 0.8, 3); },
      tick: function (k) { if (!drum) tone(160 + k * 22, 0, 0.07, 'triangle', 0.09); },
      rollStop: function (sec) { if (drum) fade(drum, sec == null ? 0.15 : sec); drum = null; },
      fanfare: function (grand) {
        this.rollStop(0.12);
        clip('crash', grand ? 0.9 : 0.7);
        if (!clip(grand ? 'fanfare-grand' : 'fanfare', grand ? 0.95 : 0.85)) synthFanfare(grand);
        var gen = run; setTimeout(function () { if (on && gen === run) clip(grand ? 'cheer' : 'applause', grand ? 0.55 : 0.45); }, grand ? 1800 : 900);
      },
      busy: function () { return live.length > 0; },
      stop: function () { run++; drum = null; live.slice().forEach(function (x) { fade(x, 0.4); }); }
    };
  })();

  function burst() { return '<div class="rv-burst" aria-hidden="true"><b></b><b></b></div>'; }
  /* The number as one cell per character; locked cells glow, the rest roll. */
  function cells(text, locked) {
    var h = '';
    for (var i = 0; i < text.length; i++) h += text[i] === ' ' ? '<s></s>' : '<span class="' + (i < locked ? 'on' : '') + (i === locked - 1 ? ' hit' : '') + '">' + esc(text[i]) + '</span>';
    return h;
  }

  /* Plays the reveal over `host`. opts: winners, myNumbers, firstName, dayLabel, verifyHref,
     confetti() -> html, chime(), onDone(). Returns stop(). */
  function play(host, opts) {
    var p = plan(opts.winners, opts.myNumbers), timers = [], i = -1, stopped = false, topShown = false;
    var reduced = !!(root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches);
    var el = document.createElement('div');
    el.className = 'rv'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'Lucky Draw results reveal');
    el.innerHTML = (reduced ? '' : '<div class="rv-rays" aria-hidden="true"></div>' + sparkles() + matrix()) +
      '<div class="rv-fx" id="rvFx"></div><div class="rv-ladder" id="rvLadder"></div><div class="rv-body" id="rvBody"></div>' +
      '<div class="rv-ctl"><button class="rv-snd" type="button" aria-label="Sound">' + (sfx.isOn() ? '♪ On' : '♪ Off') + '</button>' +
      '<button class="rv-skip" type="button">Skip</button>' +
      '<button class="rv-x" type="button" aria-label="Close"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg></button></div>';
    host.appendChild(el); sfx.preload();
    var body = el.querySelector('#rvBody'), fx = el.querySelector('#rvFx'), ladderEl = el.querySelector('#rvLadder');
    el.querySelector('.rv-skip').addEventListener('click', function () { sfx.stop(); finale(); });
    el.querySelector('.rv-x').addEventListener('click', function () { stop(); });   /* close the reveal at any point */
    el.querySelector('.rv-snd').addEventListener('click', function (e) { e.currentTarget.textContent = sfx.toggle() ? '♪ On' : '♪ Off'; });

    function later(fn, ms) { var t = setTimeout(fn, reduced ? Math.min(ms, 60) : ms); timers.push(t); return t; }
    function clear() { timers.forEach(function (t) { clearTimeout(t); clearInterval(t); }); timers = []; }
    function stop() { if (stopped) return; stopped = true; clear(); sfx.stop(); el.classList.add('out'); setTimeout(function () { el.remove(); }, 300); if (opts.onDone) opts.onDone(); }
    function mode(cls) { el.classList.remove('rolling', 'tense', 'dim', 'rv-me'); if (cls) cls.split(' ').forEach(function (c) { el.classList.add(c); }); }

    /* Ten places from 10th up to 1st; done ones light up, the current one pulses. */
    function ladder(cur) {
      ladderEl.innerHTML = p.order.map(function (w, k) {
        return '<i class="' + (k < cur ? 'done' : k === cur ? 'now' : '') + (w.big ? ' big' : '') + (k < cur && w.mine ? ' mine' : '') + '">' + w.rank + '</i>';
      }).join('');
    }

    function intro(n) {
      body.innerHTML = '<div class="rv-k">Lucky Draw · ' + esc(opts.dayLabel || '') + '</div><div class="rv-count">' + n + '</div><div class="rv-s">Ten lucky numbers. From 10th place up to 1st.</div>';
      if (n > 1) later(function () { intro(n - 1); }, 700); else later(consolation, 700);
    }

    function next() {
      i++;
      if (i >= p.order.length) { ladder(p.order.length); later(finale, 700); return; }
      var w = p.order[i];
      ladder(i);
      if (w.big && !topShown) { topShown = true; topThree(w); return; }
      announce(w);
    }

    /* Lucky 7: the same stage as the top three, only quicker. Each number rolls in the centre, locks with a
       bell, then drops into its stub in the tray below (10th to 4th), so the tray fills as the wait goes on. */
    function consolation() {
      var list = p.order.filter(function (w) { return !w.big; });
      if (!list.length) { next(); return; }
      mode(''); ladder(0);
      body.innerHTML = '<div class="rv-k">Lucky 7 · ' + inr(list[0].amount) + ' each</div>' +
        '<div class="rv7-stage"><div class="rv-place sm" id="rv7P"></div>' +
        '<div class="rv-no sm" id="rv7N"></div><div class="rv-who sm" id="rv7W"></div></div>' +
        '<div class="rv7-tray">' + list.map(function (w, k) {
          return '<div class="rv7-stub" id="rv7S' + k + '"><span class="rv7-pl">' + ordinal(w.rank) + '</span><b class="rv7-tk"></b><span class="rv7-nm"></span></div>';
        }).join('') + '</div>';
      var place = body.querySelector('#rv7P'), no = body.querySelector('#rv7N'), who = body.querySelector('#rv7W');
      (function step(k) {
        if (k >= list.length) {
          var me = list.some(function (x) { return x.mine; });
          if (me) { el.classList.add('rv-me'); if (opts.chime) opts.chime(); fx.innerHTML = reduced ? '' : (opts.confetti ? opts.confetti() : ''); }
          place.textContent = ''; no.innerHTML = ''; no.className = 'rv-no sm idle'; who.textContent = 'Seven lucky numbers drawn'; sfx.flourish();
          later(function () { fx.innerHTML = ''; i = list.length - 1; next(); }, 1600);
          return;
        }
        var w = list[k], stub = body.querySelector('#rv7S' + k), locked = 0;
        stub.classList.add('now');
        place.textContent = ordinal(w.rank); place.style.animation = 'none'; void place.offsetWidth; place.style.animation = '';
        no.className = 'rv-no sm'; who.textContent = 'Drawing…';
        mode('rolling');
        var flick = setInterval(function () { no.innerHTML = cells(scrambleFrame(w.ticket, locked, Math.random()), locked); }, 45);
        timers.push(flick);
        (function lockNext() {
          later(function () {
            locked++;
            while (locked < w.ticket.length && w.ticket[locked] === ' ') locked++;
            no.innerHTML = cells(scrambleFrame(w.ticket, locked, Math.random()), locked);
            if (locked < w.ticket.length) { lockNext(); return; }
            clearInterval(flick); mode('');
            no.innerHTML = cells(w.ticket, w.ticket.length); no.className = 'rv-no sm done';
            who.innerHTML = w.mine ? '<b class="rv-you">That’s you!</b>' : esc(w.name || '');
            sfx.ding(k);
            later(function () {
              stub.classList.remove('now'); stub.classList.add('in'); if (w.mine) stub.classList.add('mine');
              stub.querySelector('.rv7-tk').textContent = w.ticket;
              stub.querySelector('.rv7-nm').textContent = w.mine ? 'You!' : (w.name || '');
              ladder(k + 1);
              later(function () { step(k + 1); }, 250);
            }, 650);
          }, locked === 0 ? 350 : 75);
        })();
      })(0);
    }

    /* A pause before the main prizes: the lights go down. */
    function topThree(w) {
      mode('dim');
      body.innerHTML = '<div class="rv-k">Seven lucky numbers drawn</div><div class="rv-title rv-rise">And now,<br>the top three</div>' +
        '<div class="rv-s">' + inr(p.order.filter(function (x) { return x.big; }).reduce(function (t, x) { return t + x.amount; }, 0)) + ' in main prizes</div>';
      later(function () { announce(w); }, 2400);
    }

    /* Name the place first, then roll the number. 1st place gets the longest wait. */
    function announce(w) {
      mode(w.big ? 'dim' : '');
      body.innerHTML = '<div class="rv-k">' + (w.rank === 1 ? 'The grand prize' : w.big ? 'Main prize' : 'Lucky number') + '</div>' +
        '<div class="rv-place' + (w.big ? ' big' : '') + (w.rank === 1 ? ' grand' : '') + '">' + ordinal(w.rank) + '</div>' +
        '<div class="rv-prize' + (w.big ? ' big' : '') + '">' + inr(w.amount) + '</div>' +
        '<div class="rv-no" id="rvNo">' + cells(scrambleFrame(w.ticket, 0, Math.random()), 0) + '</div><div class="rv-who" id="rvWho">Drawing…</div>';
      later(function () { roll(w); }, w.rank === 1 ? 1800 : w.big ? 1300 : 700);
    }

    function roll(w) {
      var no = body.querySelector('#rvNo'), locked = 0, chars = w.ticket.replace(/ /g, '').length, n = 0;
      var base = w.rank === 1 ? 330 : w.big ? 240 : 105;
      mode('rolling' + (w.big ? ' tense' : ''));
      if (w.big) sfx.rollStart();
      var flick = setInterval(function () { no.innerHTML = cells(scrambleFrame(w.ticket, locked, Math.random()), locked); }, 50);
      timers.push(flick);
      (function lockNext() {
        n++;
        /* Slows down as it nears the end; the last character holds longest. */
        var wait = locked === 0 ? 500 : base * (1 + n * (w.big ? 0.18 : 0.06)) + (n === chars ? (w.rank === 1 ? 1500 : w.big ? 900 : 250) : 0);
        later(function () {
          locked++;
          while (locked < w.ticket.length && w.ticket[locked] === ' ') locked++;
          no.innerHTML = cells(scrambleFrame(w.ticket, locked, Math.random()), locked);
          if (w.big) sfx.tick(n);
          if (locked < w.ticket.length) { lockNext(); return; }
          clearInterval(flick); landed(w, no);
        }, wait);
      })();
    }

    function landed(w, no) {
      no.innerHTML = cells(w.ticket, w.ticket.length); no.classList.add('done');
      mode(w.mine ? 'rv-me' : '');
      ladder(i + 1);
      var who = body.querySelector('#rvWho');
      who.innerHTML = w.mine ? '<b class="rv-you">That’s you, ' + esc(opts.firstName || '') + '!</b>' : esc(w.name || '');
      if (w.big) sfx.fanfare(w.rank === 1); else sfx.ding(0);
      if (w.mine && opts.chime) opts.chime();
      fx.innerHTML = reduced ? '' : burst() + (w.big ? balloons() : '') + ((w.big || w.mine) && opts.confetti ? opts.confetti() : '');
      later(function () { fx.innerHTML = ''; next(); }, w.rank === 1 ? 3200 : w.big || w.mine ? 2400 : 1300);
    }

    function finale() {
      clear(); mode(''); el.classList.add('rv-end'); ladderEl.innerHTML = '';
      var o = p.outcome, best = p.order.filter(function (w) { return w.mine; }).sort(function (a, b) { return a.rank - b.rank; })[0];
      var rows = p.order.slice().reverse().map(function (w) {
        return '<div class="rv-row' + (w.mine ? ' mine' : '') + (w.big ? ' big' : '') + '"><span>' + ordinal(w.rank) + '</span><b>' + esc(w.ticket) + '</b><em>' + inr(w.amount) + '</em></div>';
      }).join('');
      body.innerHTML = (o.won
        ? '<div class="rv-k">Congratulations</div><div class="rv-title">You won ' + inr(o.amount) + '!</div><div class="rv-s">' + esc(opts.firstName || '') + ', your ticket took ' + ordinal(best.rank) + ' place. Claim it from My wins.</div>'
        : '<div class="rv-k">' + (o.entered ? 'Not this time' : 'Tonight’s winners') + '</div><div class="rv-title">' + (o.entered ? 'Better luck next time' : 'Ten lucky numbers') + '</div>' +
          '<div class="rv-s">' + (o.entered ? 'Every pack of Boche Tea brings new lucky numbers for tomorrow’s draw.' : 'Buy any tea pack to join tomorrow’s draw.') + '</div>') +
        '<div class="rv-list">' + rows + '</div>' +
        '<button class="btn btn-gold mt16 rv-close" type="button">See all winners</button>' +
        (opts.verifyHref ? '<a class="rv-verify" href="' + esc(opts.verifyHref) + '">Verify this draw</a>' : '');
      fx.innerHTML = o.won ? balloons() + (opts.confetti ? opts.confetti() : '') : '';
      if (o.won) { if (!sfx.busy()) sfx.fanfare(true); if (opts.chime) opts.chime(); }
      body.querySelector('.rv-close').addEventListener('click', stop);
      var v = body.querySelector('.rv-verify'); if (v) v.addEventListener('click', stop);
      el.querySelector('.rv-skip').style.display = 'none'; el.querySelector('.rv-snd').style.display = 'none';
    }

    if (!p.order.length) { stop(); return stop; }
    if (reduced) finale(); else intro(3);
    return stop;
  }

  root.BCREVEAL = { plan: plan, scrambleFrame: scrambleFrame, play: play };
})(typeof window !== 'undefined' ? window : this);
