// Service Worker for offline support
// Cache version is automatically updated during deployment
const CACHE_VERSION = 'BUILD_TIMESTAMP'; // Will be replaced by GitHub Action
const CACHE_NAME = `balneabilidade-rj-${CACHE_VERSION}`;
const ASSETS = [
  '../index.html',
  '../js/app.js',
  '../css/styles.css',
  '../data/beachData.json',
  '../data/manifest.json',
  '../img/favicon.ico',
  '../img/favicon-16x16.png',
  '../img/favicon-32x32.png',
  '../img/apple-touch-icon.png',
  '../img/android-chrome-192x192.png',
  '../img/og-image.png'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching app assets');
        // Cache files individually to see which one fails
        return Promise.all(
          ASSETS.map(url => 
            cache.add(url).catch(err => {
              console.error('Failed to cache:', url, err);
              // Don't fail the whole install if one file fails
              return Promise.resolve();
            })
          )
        );
      })
      .then(() => {
        // Try to cache CDN resources separately (non-critical)
        return caches.open(CACHE_NAME).then((cache) => {
          return Promise.allSettled([
            cache.add('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'),
            cache.add('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js')
          ]);
        });
      })
      .then(() => {
        console.log('Service Worker installed and ready');
        return self.skipWaiting();
      })
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
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // For critical files (data, CSS, JS), try network first to get latest version
  const isAppFile = event.request.url.includes('data/beachData.json') ||
                    event.request.url.includes('/js/app.js') ||
                    event.request.url.includes('/css/styles.css');
  
  if (isAppFile) {
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

  // For all other assets, cache first strategy
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version if available
        if (response) {
          return response;
        }
        
        // Otherwise fetch from network
        return fetch(event.request)
          .then((response) => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200 || response.type === 'error') {
              return response;
            }
            
            // Clone and cache successful responses
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });
            return response;
          })
          .catch(() => {
            // If everything fails and it's a navigation request, serve index.html
            if (event.request.mode === 'navigate') {
              return caches.match('./index.html');
            }
            return new Response('Offline - resource not available', {
              status: 503,
              statusText: 'Service Unavailable'
            });
          });
      })
  );
});
