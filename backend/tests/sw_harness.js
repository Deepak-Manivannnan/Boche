// Runs the real frontend/sw.js inside a fake service-worker global and checks which requests it answers.
// Usage: node backend/tests/sw_harness.js <path-to-sw.js>  -> prints JSON {path: handled}
const fs = require("fs");
const path = process.argv[2];
const listeners = {};
const self = {
  addEventListener: (type, fn) => { listeners[type] = fn; },
  skipWaiting() {}, clients: { claim() {} },
  location: { origin: "https://boche.example" },
};
const caches = { open: async () => ({ addAll: async () => {}, put: async () => {} }), keys: async () => [], match: async () => null, delete: async () => true };
const fetch = async () => ({ clone() { return this; } });
function Request(input, init) { Object.assign(this, typeof input === "string" ? { url: input } : input, init); }
new Function("self", "caches", "fetch", "Request", fs.readFileSync(path, "utf8"))(self, caches, fetch, Request);

const result = {};
for (const [method, url] of [["GET", "/api/me"], ["GET", "/api/public/days/2026-11-10/result.json"], ["GET", "/app.js"], ["GET", "/"], ["POST", "/api/orders"]]) {
  let handled = false;
  listeners.fetch({ request: { method, url: "https://boche.example" + url }, respondWith() { handled = true; } });
  result[`${method} ${url}`] = handled;
}
const cacheName = /var CACHE = '([^']+)'/.exec(fs.readFileSync(path, "utf8"))[1];
console.log(JSON.stringify({ handled: result, cacheName }));
