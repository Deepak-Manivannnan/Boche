/* BocheClub — QR visual for the prototype.
   Draws a QR-style SVG (finder, timing and alignment patterns + seeded modules)
   that changes with the seed. Production swaps this for a real signed QR
   (e.g. member id + rotating TOTP) encoded by the backend. */
var BCQR = (function () {
  'use strict';

  function rng(seed) {
    var h = 2166136261;
    for (var i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
    return function () {
      h ^= h << 13; h ^= h >>> 17; h ^= h << 5;
      return ((h >>> 0) % 10000) / 10000;
    };
  }

  function svg(seed, size) {
    var n = 29, r = rng(seed), m = [], x, y;
    for (y = 0; y < n; y++) { m[y] = []; for (x = 0; x < n; x++) m[y][x] = r() < 0.5; }

    function finder(cx, cy) {
      for (var dy = -1; dy < 8; dy++) {
        for (var dx = -1; dx < 8; dx++) {
          var xx = cx + dx, yy = cy + dy;
          if (xx < 0 || yy < 0 || xx >= n || yy >= n) continue;
          var ring = (dx >= 0 && dx <= 6 && (dy === 0 || dy === 6)) || (dy >= 0 && dy <= 6 && (dx === 0 || dx === 6));
          var core = dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4;
          m[yy][xx] = ring || core;
        }
      }
    }
    finder(0, 0); finder(n - 7, 0); finder(0, n - 7);

    for (x = 8; x < n - 8; x++) { m[6][x] = x % 2 === 0; m[x][6] = x % 2 === 0; }

    var a = n - 9;
    for (y = -2; y <= 2; y++) for (x = -2; x <= 2; x++) m[a + y][a + x] = Math.max(Math.abs(x), Math.abs(y)) !== 1;

    // quiet zone in the centre for the logo
    var c = Math.floor(n / 2);
    for (y = c - 3; y <= c + 3; y++) for (x = c - 3; x <= c + 3; x++) m[y][x] = false;

    var d = '';
    for (y = 0; y < n; y++) for (x = 0; x < n; x++) if (m[y][x]) d += 'M' + x + ' ' + y + 'h1v1h-1z';

    return '<svg viewBox="-2 -2 ' + (n + 4) + ' ' + (n + 4) + '" width="' + size + '" height="' + size +
      '" shape-rendering="crispEdges" aria-label="Member QR code"><rect x="-2" y="-2" width="' + (n + 4) +
      '" height="' + (n + 4) + '" fill="#fff"/><path d="' + d + '" fill="#1E1810"/></svg>';
  }

  return { svg: svg };
})();
