// Network-first service worker: always tries the network, falls back to cache
// when offline. This ensures the app always loads fresh assets after a deploy.

const CACHE = 'fbc-v2';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // Don't intercept cross-origin API requests — let them go direct so real
  // errors are visible in the console. Server-side caching handles perf.
  if (new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      })
      .catch(() => caches.match(e.request).then(r => r || Response.error()))
  );
});
