/* Boche — api.js
   The one place the frontend talks to the backend. Same origin, so the httpOnly session cookie
   travels with every call; responses are JSON. Errors carry the HTTP status as e.status. */
var BCAPI = (function () {
  'use strict';

  /* The button that started a request stays disabled until the server answers, so a second tap
     can't send the same action twice. An identical POST already in flight is reused, not repeated. */
  var lastBtn = null, lastAt = 0, inFlight = {};
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('button, .btn');
    if (b) { lastBtn = b; lastAt = Date.now(); }
  }, true);
  function busy(btn, on) {
    if (!btn) return;
    if (btn.tagName === 'BUTTON') btn.disabled = on;
    btn.classList.toggle('is-busy', on);
    if (on) btn.setAttribute('aria-busy', 'true'); else btn.removeAttribute('aria-busy');
  }
  function guarded(method, path, body) {
    var key = method + ' ' + path + ' ' + JSON.stringify(body);
    if (inFlight[key]) return inFlight[key];
    var btn = lastBtn && Date.now() - lastAt < 1000 && !lastBtn.disabled ? lastBtn : null;
    lastBtn = null;
    busy(btn, true);
    function done() { delete inFlight[key]; if (btn && btn.isConnected) busy(btn, false); }
    var p = inFlight[key] = request(method, path, body);
    p.then(done, done);
    return p;
  }

  function request(method, path, body) {
    var opts = { method: method, credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
    if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch('/api' + path, opts).then(function (res) {
      return res.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
        if (!res.ok) {
          var err = new Error((data && typeof data.detail === 'string' && data.detail) || res.statusText || 'Request failed');
          err.status = res.status; err.data = data;
          throw err;
        }
        return data;
      });
    }, function (netErr) {
      var err = new Error('Network error'); err.status = 0; err.cause = netErr;
      throw err;
    });
  }

  return {
    get: function (path) { return request('GET', path); },
    post: function (path, body) { return guarded('POST', path, body === undefined ? {} : body); }
  };
})();
