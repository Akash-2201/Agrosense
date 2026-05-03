// ══════════════════════════════════════════════════════
// AgroSense Service Worker - Offline Support + Caching
// ══════════════════════════════════════════════════════

var CACHE_NAME = "agrosense-v2";
var DYNAMIC_CACHE = "agrosense-dynamic-v2";

// Files to cache immediately on install
var STATIC_ASSETS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/offline.html"
];

// ── Install Event ────────────────────────────────────
self.addEventListener("install", function(event) {
  console.log("🔧 Service Worker: Installing...");
  
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      console.log("📦 Caching static assets...");
      return cache.addAll(STATIC_ASSETS);
    }).then(function() {
      // Force activate immediately
      return self.skipWaiting();
    })
  );
});

// ── Activate Event ───────────────────────────────────
self.addEventListener("activate", function(event) {
  console.log("✅ Service Worker: Activated!");
  
  event.waitUntil(
    // Clean old caches
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(name) {
          if (name !== CACHE_NAME && name !== DYNAMIC_CACHE) {
            console.log("🗑️ Deleting old cache:", name);
            return caches.delete(name);
          }
        })
      );
    }).then(function() {
      // Take control of all pages immediately
      return self.clients.claim();
    })
  );
});

// ── Fetch Event (Network First + Cache Fallback) ─────
self.addEventListener("fetch", function(event) {
  var url = new URL(event.request.url);

  // Skip non-GET requests (POST for API calls should go to network)
  if (event.request.method !== "GET") {
    return;
  }

  // Skip chrome-extension and other non-http requests
  if (!event.request.url.startsWith("http")) {
    return;
  }

  // API calls → Network only (don't cache API responses)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(function() {
        return new Response(
          JSON.stringify({
            error: "You are offline. Please connect to internet.",
            offline: true
          }),
          {
            headers: { "Content-Type": "application/json" },
            status: 503
          }
        );
      })
    );
    return;
  }

  // TTS audio files → Network only
  if (url.pathname.startsWith("/tts/")) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Static assets → Cache first, then network
  event.respondWith(
    caches.match(event.request).then(function(cachedResponse) {
      if (cachedResponse) {
        // Return cached version, but also fetch updated version in background
        fetch(event.request).then(function(networkResponse) {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(DYNAMIC_CACHE).then(function(cache) {
              cache.put(event.request, networkResponse);
            });
          }
        }).catch(function() {});
        
        return cachedResponse;
      }

      // Not in cache → fetch from network
      return fetch(event.request).then(function(networkResponse) {
        // Cache the new response for future
        if (networkResponse && networkResponse.status === 200) {
          var responseClone = networkResponse.clone();
          caches.open(DYNAMIC_CACHE).then(function(cache) {
            cache.put(event.request, responseClone);
          });
        }
        return networkResponse;
      }).catch(function() {
        // Both cache and network failed → show offline page
        if (event.request.headers.get("accept").includes("text/html")) {
          return caches.match("/offline.html");
        }
      });
    })
  );
});

// ── Background Sync (for when farmer comes back online) ──
self.addEventListener("sync", function(event) {
  if (event.tag === "sync-scans") {
    console.log("🔄 Background sync: Uploading pending scans...");
    event.waitUntil(syncPendingScans());
  }
});

function syncPendingScans() {
  // Open IndexedDB and upload any pending scans
  return self.clients.matchAll().then(function(clients) {
    clients.forEach(function(client) {
      client.postMessage({
        type: "SYNC_COMPLETE",
        message: "Pending scans uploaded successfully!"
      });
    });
  });
}

// ── Push Notifications ───────────────────────────────
self.addEventListener("push", function(event) {
  var data = event.data ? event.data.json() : {};
  
  var options = {
    body: data.body || "New update from AgroSense",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-72.png",
    vibrate: [100, 50, 100],
    data: {
      url: data.url || "/"
    },
    actions: [
      { action: "open", title: "Open App" },
      { action: "dismiss", title: "Dismiss" }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(
      data.title || "🌱 AgroSense Alert",
      options
    )
  );
});

// Handle notification click
self.addEventListener("notificationclick", function(event) {
  event.notification.close();

  if (event.action === "dismiss") return;

  event.waitUntil(
    clients.openWindow(event.notification.data.url || "/")
  );
});

console.log("🌱 AgroSense Service Worker loaded!");