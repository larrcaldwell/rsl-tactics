// App shell cached for instant load. Data files are network-first so match day is always fresh.
var SHELL = "rsl-shell-v1";
var FILES = ["./", "index.html", "style.css", "app.js", "glossary.js", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"];
self.addEventListener("install", function (e) { e.waitUntil(caches.open(SHELL).then(function (c) { return c.addAll(FILES); }).then(function () { return self.skipWaiting(); })); });
self.addEventListener("activate", function (e) { e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== SHELL && k !== "rsl-data"; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); })); });
self.addEventListener("fetch", function (e) {
  var u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  if (u.pathname.indexOf("/data/") > -1) {
    e.respondWith(fetch(e.request).then(function (r) { var cp = r.clone(); caches.open("rsl-data").then(function (c) { c.put(e.request, cp); }); return r; }).catch(function () { return caches.match(e.request); }));
  } else {
    e.respondWith(caches.match(e.request).then(function (m) { return m || fetch(e.request); }));
  }
});
