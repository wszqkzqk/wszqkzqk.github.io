const CACHE_PREFIX = "wszqkzqk-blog-";
const PRECACHE = `${CACHE_PREFIX}precache-v2`;
const RUNTIME = `${CACHE_PREFIX}runtime-v2`;
const OFFLINE_URL = "/offline.html";
const PRECACHE_URLS = [
  OFFLINE_URL,
  "/css/bootstrap.min.css",
  "/css/wszqkzqk-blog.min.css",
  "/img/404-bg.webp"
];
const CURRENT_CACHES = new Set([PRECACHE, RUNTIME]);
const STATIC_DESTINATIONS = new Set(["style", "script", "image", "font", "manifest"]);
const MAX_RUNTIME_ENTRIES = 100;

async function trimCache(cache) {
  const keys = await cache.keys();
  const expired = keys.slice(0, Math.max(0, keys.length - MAX_RUNTIME_ENTRIES));
  await Promise.all(expired.map(key => cache.delete(key)));
}

async function cacheResponse(cache, request, response) {
  if (!response.ok) {
    return;
  }
  try {
    await cache.put(request, response);
    await trimCache(cache);
  } catch {
  }
}

async function networkFirstPage(event) {
  const cache = await caches.open(RUNTIME);
  try {
    const response = await fetch(event.request);
    await cacheResponse(cache, event.request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(event.request);
    return cached || (await caches.match(OFFLINE_URL)) || Response.error();
  }
}

function staleWhileRevalidate(event) {
  const cachePromise = caches.open(RUNTIME);
  const cached = cachePromise.then(cache => cache.match(event.request));
  const fetched = fetch(event.request).then(async response => {
    const cache = await cachePromise;
    await cacheResponse(cache, event.request, response.clone());
    return response;
  });

  event.waitUntil(fetched.catch(() => {}));
  event.respondWith(cached.then(response => response || fetched));
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(PRECACHE);
    await cache.addAll(PRECACHE_URLS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    const expired = keys.filter(key => !CURRENT_CACHES.has(key)
      && (key.startsWith(CACHE_PREFIX) || key === "precache-v1" || key === "runtime"));
    await Promise.all(expired.map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(networkFirstPage(event));
  } else if (STATIC_DESTINATIONS.has(event.request.destination)) {
    staleWhileRevalidate(event);
  }
});
