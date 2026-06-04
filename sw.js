const CACHE = 'scorecard-v1';
const ASSETS = [
  './', './index.html', './404.html',
  './manifest.json',
  './assets/icons/icon-192.png', './assets/icons/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400;1,600&family=DM+Sans:wght@300;400;500;600&display=swap'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

// Network-first for our own files (always get the latest deploy), with a
// cache fallback so the app still works offline. Cross-origin requests
// (e.g. Google Fonts) stay cache-first for speed. The Apps Script backend
// is never cached so score submissions always go to the live server.
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Never intercept the Google Apps Script backend.
  if (url.hostname.endsWith('script.google.com')) return;

  const sameOrigin = url.origin === self.location.origin;

  if (sameOrigin) {
    e.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then(c => c || caches.match('./index.html')))
    );
  } else {
    e.respondWith(
      caches.match(req).then(c => c || fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(cache => cache.put(req, copy));
        return res;
      }))
    );
  }
});
