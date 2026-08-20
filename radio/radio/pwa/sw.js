// Service Worker：缓存应用壳，让面板可“安装到主屏”并离线打开。
// 实时音频流 / API / 录音文件一律不缓存，永远走网络。
const CACHE = 'pyradio-shell-v1';
const SHELL = ['/', '/icon-192.png', '/icon-512.png', '/manifest.webmanifest'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/stream') ||
      url.pathname.startsWith('/recordings') ||
      url.pathname.startsWith('/api/')) {
    return; // 实时内容不拦截
  }
  // 网络优先，失败回退到缓存壳
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request).then(r => r || caches.match('/')))
  );
});
