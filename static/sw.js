// TruckSpot Service Worker — v9
// Kluczowa zmiana: HTML zawsze network-first → apka zawsze ładuje świeży kod
const STATIC_CACHE = 'ts-static-v10';  // ikony, manifest (rzadko się zmieniają)
const DATA_CACHE   = 'ts-data-v10';    // API responses
const TILE_CACHE   = 'ts-tiles-v10';   // kafelki mapy

// Tylko naprawdę statyczne assety — NIE cachujemy HTML
const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/icon-144.png',
];

const DATA_PATTERNS = [
  /\/api\/parkings/,
  /\/api\/spots/,
  /\/api\/markets/,
  /\/api\/occupancy/,
];

const TILE_PATTERN = /mt\d\.google\.com|tile\.openstreetmap/;

// ── INSTALL ──────────────────────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => Promise.allSettled(
        STATIC_ASSETS.map(url => cache.add(url).catch(() => {}))
      ))
      .then(() => self.skipWaiting())
  );
});

// ── ACTIVATE — wyczyść stare cache ───────────────────────────────────────────
self.addEventListener('activate', e => {
  const CURRENT = [STATIC_CACHE, DATA_CACHE, TILE_CACHE];
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => !CURRENT.includes(k)).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window', includeUncontrolled: true }))
      .then(clients => {
        // Jeśli żaden klient nie jest aktywny (app była w tle/zamknięta)
        // — przeładuj cicho bez bannera
        const activeClients = clients.filter(c => c.visibilityState === 'visible');
        if(activeClients.length === 0){
          // Nikt nie patrzy — przeładuj wszystkich po cichu
          clients.forEach(c => c.navigate(c.url));
        } else {
          // Ktoś jest aktywnie w apce — pokaż banner
          activeClients.forEach(c => c.postMessage({ type: 'UPDATE_AVAILABLE' }));
        }
      })
  );
});

// ── FETCH ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const { request } = e;
  const url = request.url;

  if (request.method !== 'GET') return;
  if (url.startsWith('chrome-extension://')) return;

  // 1. MAP TILES — Cache First
  if (TILE_PATTERN.test(url)) {
    e.respondWith(tileStrategy(request));
    return;
  }

  // 2. API DATA — Stale-While-Revalidate
  if (DATA_PATTERNS.some(p => p.test(url))) {
    e.respondWith(staleWhileRevalidate(request, DATA_CACHE));
    return;
  }

  // 3. STATYCZNE ASSETY (ikony, manifest) — Cache First
  if (STATIC_ASSETS.some(a => url.endsWith(a))) {
    e.respondWith(cacheFirst(request));
    return;
  }

  // 4. HTML (nawigacja) i wszystko inne — NETWORK FIRST
  // → zawsze świeży kod z serwera, cache tylko jako fallback offline
  e.respondWith(networkFirst(request));
});

// ── STRATEGIE ─────────────────────────────────────────────────────────────────

// Network First — próbuj sieć, fallback na cache
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    if (request.mode === 'navigate') {
      return new Response('<h1>Offline</h1><p>Brak połączenia. Otwórz apkę gdy masz internet.</p>',
        { headers: { 'Content-Type': 'text/html' } });
    }
    return new Response('', { status: 503 });
  }
}

// Cache First — zwróć z cache, jeśli brak idź do sieci
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

// Stale-While-Revalidate
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const networkPromise = fetch(request).then(r => {
    if (r.ok) cache.put(request, r.clone());
    return r;
  }).catch(() => null);
  return cached || await networkPromise || new Response('', { status: 503 });
}

// Kafelki mapy — Cache First z limitem 600
const TILE_MAX = 600;
async function tileStrategy(request) {
  const cache = await caches.open(TILE_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const keys = await cache.keys();
      if (keys.length >= TILE_MAX) {
        for (let i = 0; i < 50; i++) cache.delete(keys[i]);
      }
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

// ── PUSH NOTIFICATIONS ────────────────────────────────────────────────────────
const CAT_VIBRATE = {
  police:   [200, 100, 200, 100, 200],
  accident: [300, 100, 300],
  help:     [500, 100, 500],
  roadwork: [100, 50, 100],
  weather:  [100, 50, 100, 50, 100],
};

self.addEventListener('push', e => {
  let payload = { title: 'TruckSpot', body: 'Nowy alert w pobliżu' };
  try { payload = e.data?.json() || payload; } catch(err) {}
  const cat = payload.data?.cat || 'info';
  const lat = payload.data?.lat;
  const lng = payload.data?.lng;
  const openUrl = lat && lng ? `/?alert_lat=${lat}&alert_lng=${lng}&alert_cat=${cat}` : '/';
  e.waitUntil(self.registration.showNotification(payload.title, {
    body: payload.body,
    icon: '/static/icon-192.png',
    badge: '/static/favicon-32.png',
    tag: payload.tag || `cb-${cat}`,
    renotify: true,
    vibrate: CAT_VIBRATE[cat] || [200, 100, 200],
    data: { url: openUrl, lat, lng, cat },
    actions: [
      { action: 'navigate', title: '🗺️ Pokaż na mapie' },
      { action: 'dismiss',  title: '✕ Zamknij' },
    ],
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'dismiss') return;
  const url = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => c.url.includes(self.location.origin));
      if (existing) {
        existing.focus();
        existing.postMessage({ type: 'ALERT_NAVIGATE', url,
          lat: e.notification.data?.lat, lng: e.notification.data?.lng });
      } else {
        clients.openWindow(url);
      }
    })
  );
});
