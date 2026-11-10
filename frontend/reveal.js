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

  function matrix() {
    var cols = '';
    for (var i = 0; i < 16; i++) {
      var s = ''; for (var k = 0; k < 28; k++) s += Math.random() < 0.5 ? '0' : '1';
      cols += '<i style="left:' + (i * 6.4 + 1) + '%;animation-duration:' + (5 + Math.random() * 6).toFixed(1) + 's;animation-delay:-' + (Math.random() * 6).toFixed(1) + 's">' + s + '</i>';
    }
    return '<div class="rv-matrix" aria-hidden="true">' + cols + '</div>';
  }
  function balloons() {
    var cols = ['#D9B45A', '#B3261E', '#2F7A4C', '#F5E2A8', '#C9A04A', '#8C6420'], h = '';
    for (var i = 0; i < 9; i++) h += '<i style="left:' + (6 + i * 10.5) + '%;background:' + cols[i % cols.length] + ';animation-delay:' + (i * 0.12).toFixed(2) + 's;animation-duration:' + (2.6 + (i % 3) * 0.5).toFixed(1) + 's"></i>';
    return '<div class="rv-balloons" aria-hidden="true">' + h + '</div>';
  }

  /* Plays the reveal over `host`. opts: winners, myNumbers, firstName, dayLabel, verifyHref,
     confetti() -> html, chime(), onDone(). Returns stop(). */
  function play(host, opts) {
    var p = plan(opts.winners, opts.myNumbers), timers = [], i = -1, stopped = false;
    var reduced = !!(root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches);
    var el = document.createElement('div');
    el.className = 'rv'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'Lucky Draw results reveal');
    el.innerHTML = (reduced ? '' : matrix()) + '<div class="rv-fx" id="rvFx"></div><div class="rv-body" id="rvBody"></div>' +
      '<button class="rv-skip" type="button">Skip</button>';
    host.appendChild(el);
    var body = el.querySelector('#rvBody'), fx = el.querySelector('#rvFx');
    el.querySelector('.rv-skip').addEventListener('click', function () { finale(); });

    function later(fn, ms) { var t = setTimeout(fn, reduced ? Math.min(ms, 60) : ms); timers.push(t); return t; }
    function clear() { timers.forEach(function (t) { clearTimeout(t); clearInterval(t); }); timers = []; }
    function stop() { if (stopped) return; stopped = true; clear(); el.classList.add('out'); setTimeout(function () { el.remove(); }, 300); if (opts.onDone) opts.onDone(); }

    function intro(n) {
      body.innerHTML = '<div class="rv-k">Lucky Draw · ' + esc(opts.dayLabel || '') + '</div><div class="rv-count">' + n + '</div><div class="rv-s">Ten winners. Lowest prize first.</div>';
      if (n > 1) later(function () { intro(n - 1); }, 750); else later(next, 750);
    }

    function next() {
      i++;
      if (i >= p.order.length) { later(finale, 600); return; }
      var w = p.order[i], locked = 0, step = w.big ? 230 : 120;
      body.innerHTML = '<div class="rv-k">' + (w.big ? 'Main prize' : 'Lucky 7 · ' + (i + 1) + ' of 7') + '</div>' +
        '<div class="rv-prize' + (w.big ? ' big' : '') + '">' + esc(w.label) + ' · ' + inr(w.amount) + '</div>' +
        '<div class="rv-no" id="rvNo">' + esc(scrambleFrame(w.ticket, 0, Math.random())) + '</div><div class="rv-who" id="rvWho"></div>';
      var no = body.querySelector('#rvNo');
      var flick = setInterval(function () { no.textContent = scrambleFrame(w.ticket, locked, Math.random()); }, 45);
      timers.push(flick);
      (function lockNext() {
        later(function () {
          locked++;
          while (locked < w.ticket.length && w.ticket[locked] === ' ') locked++;
          if (locked < w.ticket.length) { lockNext(); return; }
          clearInterval(flick); no.textContent = w.ticket; no.classList.add('done');
          var who = body.querySelector('#rvWho');
          who.innerHTML = w.mine ? '<b class="rv-you">That’s you, ' + esc(opts.firstName || '') + '!</b>' : esc(w.name || '');
          if (w.mine) { el.classList.add('rv-me'); if (opts.chime) opts.chime(); }
          if (w.big || w.mine) fx.innerHTML = (w.big ? balloons() : '') + (opts.confetti ? opts.confetti() : '');
          later(function () { fx.innerHTML = ''; el.classList.remove('rv-me'); next(); }, w.big || w.mine ? 2100 : 1100);
        }, locked === 0 ? 450 : step);
      })();
    }

    function finale() {
      clear(); el.classList.add('rv-end');
      var o = p.outcome, rows = p.order.slice().reverse().map(function (w) {
        return '<div class="rv-row' + (w.mine ? ' mine' : '') + '"><span>' + esc(w.label) + '</span><b>' + esc(w.ticket) + '</b></div>';
      }).join('');
      body.innerHTML = (o.won
        ? '<div class="rv-k">Congratulations</div><div class="rv-title">You won ' + inr(o.amount) + '!</div><div class="rv-s">' + esc(opts.firstName || '') + ', your ticket took the ' + esc(o.best) + '. Claim it from My wins.</div>'
        : '<div class="rv-k">' + (o.entered ? 'Not this time' : 'Tonight’s winners') + '</div><div class="rv-title">' + (o.entered ? 'Better luck next time' : 'Ten lucky numbers') + '</div>' +
          '<div class="rv-s">' + (o.entered ? 'Every pack of Boche Tea brings new lucky numbers for tomorrow’s draw.' : 'Buy any tea pack to join tomorrow’s draw.') + '</div>') +
        '<div class="rv-list">' + rows + '</div>' +
        '<button class="btn btn-gold mt16 rv-close" type="button">See all winners</button>' +
        (opts.verifyHref ? '<a class="rv-verify" href="' + esc(opts.verifyHref) + '">Verify this draw</a>' : '');
      fx.innerHTML = o.won ? balloons() + (opts.confetti ? opts.confetti() : '') : '';
      if (o.won && opts.chime) opts.chime();
      body.querySelector('.rv-close').addEventListener('click', stop);
      var v = body.querySelector('.rv-verify'); if (v) v.addEventListener('click', stop);
      el.querySelector('.rv-skip').style.display = 'none';
    }

    if (!p.order.length) { stop(); return stop; }
    if (reduced) finale(); else intro(3);
    return stop;
  }

  root.BCREVEAL = { plan: plan, scrambleFrame: scrambleFrame, play: play };
})(typeof window !== 'undefined' ? window : this);
