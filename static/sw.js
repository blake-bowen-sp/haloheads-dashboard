const CACHE = "haloheads-v4";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  // drop the old cache-first cache (incl. the stale "/") and take control now
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => (k === CACHE ? null : caches.delete(k)))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const req = e.request;
  const isHTML =
    req.mode === "navigate" || (req.headers.get("accept") || "").includes("text/html");

  if (isHTML) {
    // network-first: always show the latest deploy; fall back to cache only offline
    e.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req))
    );
  } else {
    // static assets: cache-first, populate on first fetch (bump CACHE to invalidate)
    e.respondWith(
      caches.match(req).then(
        cached =>
          cached ||
          fetch(req).then(res => {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(req, copy));
            return res;
          })
      )
    );
  }
});
