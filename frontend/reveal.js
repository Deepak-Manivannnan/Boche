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
  /* Synthesised sounds (Web Audio, no files): a soft bell per consolation number, a rising drum tick while
     a top-three number locks, and a brass-like fanfare for 3rd/2nd, bigger for 1st. Muting is remembered. */
  var sfx = (function () {
    var ctx = null, on = true;
    try { on = root.localStorage.getItem('bocheclub-rv-sound') !== 'off'; } catch (e) { on = true; }
    function ac() {
      if (!on) return null;
      if (!ctx) { var C = root.AudioContext || root.webkitAudioContext; if (!C) return null; try { ctx = new C(); } catch (e) { return null; } }
      if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
      return ctx;
    }
    function tone(f, t0, dur, type, vol) {
      var c = ac(); if (!c) return;
      var o = c.createOscillator(), g = c.createGain(), t = c.currentTime + t0;
      o.type = type || 'sine'; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol || 0.15, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + dur + 0.05);
    }
    return {
      isOn: function () { return on; },
      toggle: function () { on = !on; try { root.localStorage.setItem('bocheclub-rv-sound', on ? 'on' : 'off'); } catch (e) {} return on; },
      tick: function (k) { tone(160 + k * 22, 0, 0.07, 'triangle', 0.09); },
      ding: function (k) { var f = [784, 880, 988, 1047, 1175, 1319, 1568][k % 7]; tone(f, 0, 0.6, 'sine', 0.16); tone(f * 2, 0, 0.3, 'sine', 0.04); },
      fanfare: function (grand) {
        var run = grand ? [392, 523, 659, 784, 1047] : [523, 659, 784];
        run.forEach(function (f, i) { tone(f, i * 0.11, 0.5, 'sawtooth', 0.05); tone(f, i * 0.11, 0.5, 'triangle', 0.12); });
        var at = run.length * 0.11, hold = grand ? 2.2 : 1.3;
        [523, 659, 784, 1047].concat(grand ? [1319] : []).forEach(function (f) { tone(f, at, hold, 'triangle', 0.1); tone(f, at, hold, 'sawtooth', 0.025); });
        tone(131, at, hold, 'sine', 0.18);
        if (grand) for (var k = 0; k < 10; k++) tone(1568 + Math.random() * 1400, at + 0.25 + k * 0.12, 0.25, 'sine', 0.05);
      }
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
      '<button class="rv-snd" type="button" aria-label="Sound">' + (sfx.isOn() ? '♪ On' : '♪ Off') + '</button><button class="rv-skip" type="button">Skip</button>';
    host.appendChild(el);
    var body = el.querySelector('#rvBody'), fx = el.querySelector('#rvFx'), ladderEl = el.querySelector('#rvLadder');
    el.querySelector('.rv-skip').addEventListener('click', function () { finale(); });
    el.querySelector('.rv-snd').addEventListener('click', function (e) { e.currentTarget.textContent = sfx.toggle() ? '♪ On' : '♪ Off'; });

    function later(fn, ms) { var t = setTimeout(fn, reduced ? Math.min(ms, 60) : ms); timers.push(t); return t; }
    function clear() { timers.forEach(function (t) { clearTimeout(t); clearInterval(t); }); timers = []; }
    function stop() { if (stopped) return; stopped = true; clear(); el.classList.add('out'); setTimeout(function () { el.remove(); }, 300); if (opts.onDone) opts.onDone(); }
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

    /* Lucky 7: a board of seven rows (10th at the top, 4th at the bottom). One row at a time lights up,
       rolls for about a second and locks with a bell, then the next row starts. ~7 s in all. */
    function consolation() {
      var list = p.order.filter(function (w) { return !w.big; });
      if (!list.length) { next(); return; }
      mode(''); ladder(0);
      body.innerHTML = '<div class="rv-k">Lucky 7 · consolation prizes</div><div class="rv-prize">' + inr(list[0].amount) + ' each</div>' +
        '<div class="rv-board">' + list.map(function (w, k) {
          return '<div class="rv-row7" id="rvG' + k + '"><span class="rv-pl">' + ordinal(w.rank) + '</span>' +
            '<span class="rv-tk">' + esc(w.ticket.replace(/[A-Z0-9]/g, '•')) + '</span><span class="rv-nm"></span></div>';
        }).join('') + '</div>';
      (function step(k) {
        if (k >= list.length) {
          var me = list.some(function (x) { return x.mine; });
          if (me) { el.classList.add('rv-me'); if (opts.chime) opts.chime(); fx.innerHTML = reduced ? '' : (opts.confetti ? opts.confetti() : ''); }
          later(function () { fx.innerHTML = ''; i = list.length - 1; next(); }, 1800);
          return;
        }
        var w = list[k], row = body.querySelector('#rvG' + k), tk = row.querySelector('.rv-tk');
        row.classList.add('live'); mode('rolling');
        var flick = setInterval(function () { tk.textContent = scrambleFrame(w.ticket, 0, Math.random()); }, 55);
        timers.push(flick);
        later(function () {
          clearInterval(flick); mode('');
          tk.textContent = w.ticket;
          row.classList.remove('live'); row.classList.add('done');
          var nm = row.querySelector('.rv-nm');
          if (w.mine) { row.classList.add('mine'); nm.innerHTML = '<b>You!</b>'; } else nm.textContent = w.name || '';
          ladder(k + 1); sfx.ding(k);
          later(function () { step(k + 1); }, 260);
        }, 750);
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
      if (o.won) { sfx.fanfare(true); if (opts.chime) opts.chime(); }
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
