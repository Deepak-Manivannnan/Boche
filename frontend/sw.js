/* BocheClub service worker ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â caches the app shell so the card opens offline */
var CACHE = 'bocheclub-v165';
var SHELL = ['/', '/index.html', '/app.css', '/app.js', '/api.js', '/reveal.js', '/data.js', '/qr.js', '/manifest.json', '/icons/icon.svg', '/icons/icon-192.png', '/icons/icon-512.png', '/img/portrait.webp', '/img/member.webp', '/img/shakesbierre.png'];
/* 'reload' / 'no-cache': never take the shell from the browser's HTTP cache, which can hold a copy from before a deploy */
self.addEventListener('install', function (e) { e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL.map(function (u) { return new Request(u, { cache: 'reload' }); })); })); self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (k) { return Promise.all(k.filter(function (x) { return x !== CACHE; }).map(function (x) { return caches.delete(x); })); }));
  self.clients.claim();
});
self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  if (new URL(e.request.url).pathname.indexOf('/api/') === 0) return;   /* live data: never served from cache */
  var req = e.request.mode === 'navigate' ? e.request : new Request(e.request, { cache: 'no-cache' });   /* a navigate request can't be re-made */
  e.respondWith(fetch(req).then(function (r) {
    var copy = r.clone(); caches.open(CACHE).then(function (c) { c.put(e.request, copy); }); return r;
  }).catch(function () {   /* offline: an app route such as /draw opens the cached app */
    return caches.match(e.request).then(function (hit) { return hit || (e.request.mode === 'navigate' ? caches.match('/index.html') : hit); });
  }));
});
