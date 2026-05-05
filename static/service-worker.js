self.addEventListener('install', (e) => {
  console.log('[Service Worker] Install');
});

self.addEventListener('fetch', (e) => {
  // Basic fetch handler (required for PWA detection)
  e.respondWith(
    fetch(e.request).catch(() => {
      return new Response("Offline mode not yet supported fully.");
    })
  );
});
