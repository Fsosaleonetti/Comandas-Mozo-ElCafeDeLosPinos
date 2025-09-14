const CACHE = 'mozo-cache-1757341762';
const OFFLINE_URLS = [
  '/static/mozo.html',
  '/static/manifest.mozo.webmanifest',
  '/static/icons/mozo-192.png',
  '/static/icons/mozo-512.png'
];
self.addEventListener('install', (e)=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(OFFLINE_URLS)));
  self.skipWaiting();
});
self.addEventListener('activate', (e)=>{
  e.waitUntil((async()=>{
    const keys = await caches.keys();
    await Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (e)=>{
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    e.respondWith((async()=>{
      try{
        const net = await fetch(req);
        const cache = await caches.open(CACHE);
        cache.put(req, net.clone());
        return net;
      }catch(err){
        const cached = await caches.match(req);
        if (cached) return cached;
        if (req.mode === 'navigate') return caches.match('/static/mozo.html');
        throw err;
      }
    })());
  }
});