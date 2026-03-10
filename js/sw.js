// Service Worker for offline support
const CACHE_NAME = 'balneabilidade-rio-v1';
const ASSETS = [
  './',
  './index.html',
  './js/app.js',
  './css/styles.css',
  './data/beachData.json',
  './data/manifest.json',
  './img/favicon.ico',
  './img/favicon-16x16.png',
  './img/favicon-32x32.png',
  './img/apple-touch-icon.png',
  './img/android-chrome-192x192.png',
  './img/og-image.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching app assets');
        return cache.addAll(ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME)
            .map((name) => caches.delete(name))
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // For beachData.json, try network first, fallback to cache
  if (event.request.url.includes('data/beachData.json')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Clone response to cache it
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // If network fails, use cached version
          return caches.match(event.request);
        })
    );
    return;
  }

  // For other assets, cache first strategy
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        if (response) {
          return response;
        }
        return fetch(event.request).then((response) => {
          // Don't cache non-successful responses
          if (!response || response.status !== 200 || response.type === 'error') {
            return response;
          }
          // Clone and cache
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
          return response;
        });
      })
  );
});
