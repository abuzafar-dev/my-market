import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import basicSsl from '@vitejs/plugin-basic-ssl'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// scripts/dev.sh regenerates ../adhoc.crt + ../adhoc.key on every run with
// a real iPAddress SAN entry for the machine's current LAN IP (shared with
// the Django backend, which reads the same two files). @vitejs/plugin-basic-ssl
// can only emit dNSName SAN entries, never a proper iPAddress one — good
// enough for Chrome's "Advanced -> Proceed" bypass, but iOS Safari treats a
// cert with no matching iPAddress entry as a hard failure with no bypass at
// all (blank page). Prefer the real cert when it's there; fall back to the
// plugin (e.g. a bare `npm run dev` never run via dev.sh) so localhost still
// gets HTTPS.
const certPath = fileURLToPath(new URL('../adhoc.crt', import.meta.url))
const keyPath = fileURLToPath(new URL('../adhoc.key', import.meta.url))
const sharedCert =
  existsSync(certPath) && existsSync(keyPath)
    ? { cert: readFileSync(certPath), key: readFileSync(keyPath) }
    : null

export default defineConfig({
  server: sharedCert ? { https: sharedCert } : undefined,
  preview: sharedCert ? { https: sharedCert } : undefined,
  plugins: [
    vue(),
    // Self-signed HTTPS for the dev server only — camera/BarcodeDetector
    // need a secure context, which plain http://<lan-ip> never is. Only
    // used as a fallback when the shared LAN-IP cert above isn't present.
    ...(sharedCert ? [] : [basicSsl()]),
    VitePWA({
      registerType: 'autoUpdate',
      // The service worker falls back to index.html for page navigations; it
      // must not do that for the Django admin, API, static files or photos.
      workbox: {
        // Fonts and the barcode decoder (.wasm) are part of the app shell, so
        // cache them for offline use too.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2,wasm}'],
        navigateFallbackDenylist: [
          /^\/api\//,
          /^\/admin\//,
          /^\/static\//,
          /^\/media\//,
          /^\/healthz\//,
        ],
      },
      manifest: {
        name: 'Mening Bozorim',
        short_name: 'Mening Bozorim',
        description: "Kichik do'konlar uchun boshqaruv tizimi",
        theme_color: '#0f172a',
        background_color: '#f8fafc',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
