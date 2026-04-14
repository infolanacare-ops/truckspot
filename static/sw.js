// TruckSpot Service Worker — offline mode v3
const SHELL_CACHE = 'ts-shell-v3';
const DATA_CACHE  = 'ts-data-v3';
const TILE_CACHE  = 'ts-tiles-v3';

// App shell — cache przy instalacji, zawsze dostępny offline
const SHELL_ASSETS = [
  '/',
  '/static/sw.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  // Leaflet z CDN
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  // Google Fonts
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Montserrat:wght@700;800;900&display=swap',
];

// API endpointy — cache + network (stale-while-revalidate)
const DATA_PATTERNS = [
  /\/api\/parkings/,
  /\/api\/spots/,
  /\/api\/markets/,
  /\/api\/occupancy/,
];

// Map tiles — cache agresywnie (nie zmieniają się)
const TILE_PATTERN = /mt\d\.google\.com|tile\.openstreetmap/;

// ── INSTALL ─────────────────────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL_CACHE).then(cache =>
      // Ignoruj błędy CDN (mogą nie być dostępne przy pierwszym ładowaniu)
      Promise.allSettled(SHELL_ASSETS.map(url =>
        cache.add(url).catch(() => console.warn('[SW] Nie można zache\'ować:', url))
      ))
    ).then(() => self.skipWaiting())
  );
});

// ── ACTIVATE — usuń stare cache ──────────────────────────────────────────────
self.addEventListener('activate', e => {
  const CURRENT = [SHELL_CACHE, DATA_CACHE, TILE_CACHE];
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => !CURRENT.includes(k)).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── FETCH — strategie cachowania ─────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const { request } = e;
  const url = request.url;

  // Ignoruj chrome-extension i non-GET
  if (request.method !== 'GET') return;
  if (url.startsWith('chrome-extension://')) return;

  // 1. MAP TILES — Cache First (bardzo agresywny, kafelki się nie zmieniają)
  if (TILE_PATTERN.test(url)) {
    e.respondWith(tileStrategy(request));
    return;
  }

  // 2. API DATA — Stale-While-Revalidate (z cache + odśwież w tle)
  if (DATA_PATTERNS.some(p => p.test(url))) {
    e.respondWith(staleWhileRevalidate(request, DATA_CACHE));
    return;
  }

  // 3. APP SHELL — Cache First z fallbackiem na sieć
  if (url.includes(self.location.origin) || SHELL_ASSETS.includes(url)) {
    e.respondWith(shellStrategy(request));
    return;
  }

  // 4. Zewnętrzne zasoby (fonts, CDN) — Cache First
  e.respondWith(shellStrategy(request));
});

// ── STRATEGIE ────────────────────────────────────────────────────────────────

// Cache First — zwróć z cache, jeśli brak idź do sieci i zapisz
async function shellStrategy(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Offline fallback — zwróć główną stronę dla nawigacji
    if (request.mode === 'navigate') {
      const cached = await caches.match('/');
      if (cached) return cached;
    }
    return offlineFallback(request);
  }
}

// Stale-While-Revalidate — zwróć cache natychmiast, odśwież w tle
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const networkPromise = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);

  // Jeśli mamy cache — zwróć od razu i odśwież w tle
  if (cached) {
    networkPromise; // odśwież w tle (fire and forget)
    return cached;
  }
  // Jeśli brak cache — czekaj na sieć
  return networkPromise || offlineFallback(request);
}

// Kafelki mapy — Cache First z limitem 500 kafelków
const TILE_MAX = 500;
async function tileStrategy(request) {
  const cache = await caches.open(TILE_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      // Ogranicz rozmiar cache kafelków
      const keys = await cache.keys();
      if (keys.length >= TILE_MAX) {
        // Usuń najstarsze 50 kafelków
        for (let i = 0; i < 50; i++) cache.delete(keys[i]);
      }
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

// Fallback gdy całkowicie offline
function offlineFallback(request) {
  if (request.destination === 'image') {
    return new Response(
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="#1a1f2e"/><text x="50" y="55" text-anchor="middle" fill="#8890a8" font-size="12">offline</text></svg>',
      { headers: { 'Content-Type': 'image/svg+xml' } }
    );
  }
  if (request.headers.get('Accept')?.includes('application/json')) {
    return new Response(JSON.stringify({ offline: true, data: [] }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  return new Response('Offline — TruckSpot', { status: 503 });
}

// ── BACKGROUND SYNC — wyślij głosy zajętości gdy wróci sieć ─────────────────
self.addEventListener('sync', e => {
  if (e.tag === 'sync-occupancy') {
    e.waitUntil(syncPendingVotes());
  }
});

async function syncPendingVotes() {
  // Pobierz oczekujące głosy z IndexedDB (gdy offline)
  // Implementacja docelowa — na razie placeholder
  console.log('[SW] Sync pending votes...');
}

// ── PUSH NOTIFICATIONS ───────────────────────────────────────────────────────
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
  const openUrl = lat && lng
    ? `/?alert_lat=${lat}&alert_lng=${lng}&alert_cat=${cat}`
    : '/';

  const options = {
    body:    payload.body,
    icon:    '/static/icon-192.png',
    badge:   '/static/favicon-32.png',
    tag:     payload.tag || `cb-${cat}`,
    renotify: true,
    vibrate: CAT_VIBRATE[cat] || [200, 100, 200],
    data:    { url: openUrl, lat, lng, cat },
    actions: [
      { action: 'navigate', title: '🗺️ Pokaż na mapie' },
      { action: 'dismiss',  title: '✕ Zamknij' },
    ],
  };

  e.waitUntil(self.registration.showNotification(payload.title, options));
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
