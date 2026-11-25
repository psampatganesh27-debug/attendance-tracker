const CACHE_NAME = 'campustrack-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Always go straight to the network so attendance data is never stale
  event.respondWith(fetch(event.request));
});