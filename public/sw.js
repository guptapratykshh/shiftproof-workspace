/* Only cache the application shell and static build assets. Never cache account/API data. */
const CACHE = 'shiftproof-shell-v1';
// Let open tabs finish using their current release. Never replace their shell
// or discard cached lazy chunks while a worker is recording or editing a draft.
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.add('/'))); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('shiftproof-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', event => {
  const request = event.request; const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.searchParams.has('token')) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/')));
  } else if ((url.pathname.startsWith('/assets/') || ['/favicon.svg', '/theme.js'].includes(url.pathname))) {
    event.respondWith(caches.match(request, { ignoreVary: true }).then(cached => cached || fetch(request).then(response => { if (response.ok) { const copy = response.clone(); void caches.open(CACHE).then(cache => cache.put(request, copy)); } return response; })));
  }
});
