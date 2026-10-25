const CACHE_NAME = 'r6-lobby-shell-v3';
const SHELL_URLS = [
  '/',
  '/app.js',
  '/i18n.js',
  '/manifest.en.webmanifest',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-512-maskable.png',
  '/icons/apple-touch-icon-r6-v2.png'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(SHELL_URLS.map(async url => {
      try {
        const response = await fetch(url, { cache: 'no-store' });
        if (response.ok) await cache.put(url, response);
      } catch {
        // A transient missing static resource should not prevent the board opening.
      }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name.startsWith('r6-lobby-shell-') && name !== CACHE_NAME).map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request, { cache: 'no-store' });
        if (response.ok) {
          const cache = await caches.open(CACHE_NAME);
          await cache.put(new URL('/', self.location.origin).href, response.clone());
        }
        return response;
      } catch {
        return (await caches.match(new URL('/', self.location.origin).href)) || new Response('Offline: reconnect to read the shared roster. / 当前离线，重新联网后可读取共享名单。', {
          status: 503,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      }
    })());
    return;
  }

  if (url.pathname.startsWith('/icons/') || SHELL_URLS.includes(url.pathname)) {
    event.respondWith((async () => {
      const cacheKey = new URL(url.pathname, self.location.origin).href;
      const cached = await caches.match(cacheKey);
      if (cached) return cached;
      const response = await fetch(request, { cache: 'no-store' });
      if (response.ok) {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(cacheKey, response.clone());
      }
      return response;
    })());
  }
});
