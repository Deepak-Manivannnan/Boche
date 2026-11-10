/* Boche — api.js
   The one place the frontend talks to the backend. Same origin, so the httpOnly session cookie
   travels with every call; responses are JSON. Errors carry the HTTP status as e.status. */
var BCAPI = (function () {
  'use strict';

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
    post: function (path, body) { return request('POST', path, body === undefined ? {} : body); }
  };
})();
