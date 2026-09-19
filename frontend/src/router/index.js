import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

// TZ v2 4.3 — one route per row of that table. The bottom nav (App.vue)
// shows on all of these except login, so none of them is a dead end.
const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  // Sales is the landing screen; there is no separate home page.
  { path: '/', redirect: { name: 'sale' } },
  { path: '/sotuv', name: 'sale', component: () => import('@/views/SaleView.vue') },
  {
    path: '/chek/:id',
    name: 'receipt',
    component: () => import('@/views/ReceiptView.vue'),
    props: true,
  },
  {
    path: '/mahsulotlar',
    name: 'products',
    component: () => import('@/views/ProductsView.vue'),
    // Shown as the header's primary button (sm and up); phones keep the
    // page's own "Yangi" button.
    meta: {
      headerAction: {
        labelKey: 'nav.new_product',
        icon: 'plus',
        to: { name: 'product-new' },
        role: 'owner',
      },
    },
  },
  {
    path: '/mahsulotlar/yangi',
    name: 'product-new',
    component: () => import('@/views/ProductFormView.vue'),
    meta: { role: 'owner' },
  },
  {
    path: '/mahsulotlar/:id',
    name: 'product-edit',
    component: () => import('@/views/ProductFormView.vue'),
    props: true,
    meta: { role: 'owner' },
  },
  {
    path: '/kirim',
    name: 'batch-new',
    component: () => import('@/views/BatchFormView.vue'),
    meta: { role: 'owner' },
  },
  { path: '/qarz', name: 'customers', component: () => import('@/views/CustomersView.vue') },
  {
    path: '/qarz/:id',
    name: 'customer-detail',
    component: () => import('@/views/CustomerDetailView.vue'),
    props: true,
  },
  {
    path: '/hisobot',
    name: 'reports',
    component: () => import('@/views/ReportsView.vue'),
    meta: { role: 'owner' },
  },
  {
    path: '/sozlamalar',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'sale' }
  }
  if (to.meta.role && auth.user?.role !== to.meta.role) {
    return { name: 'sale' }
  }
  return true
})

export default router
