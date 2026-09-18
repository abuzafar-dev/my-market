import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

// TZ v2 4.3 — one route per row of that table. The bottom nav (App.vue)
// shows on all of these except login, so none of them is a dead end.
const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/sotuv', name: 'sale', component: () => import('@/views/SaleView.vue') },
  {
    path: '/chek/:id',
    name: 'receipt',
    component: () => import('@/views/ReceiptView.vue'),
    props: true,
  },
  { path: '/mahsulotlar', name: 'products', component: () => import('@/views/ProductsView.vue') },
  {
    path: '/mahsulotlar/yangi',
    name: 'product-new',
    component: () => import('@/views/ProductFormView.vue'),
  },
  {
    path: '/mahsulotlar/:id',
    name: 'product-edit',
    component: () => import('@/views/ProductFormView.vue'),
    props: true,
  },
  { path: '/kirim', name: 'batch-new', component: () => import('@/views/BatchFormView.vue') },
  { path: '/qarz', name: 'customers', component: () => import('@/views/CustomersView.vue') },
  {
    path: '/qarz/:id',
    name: 'customer-detail',
    component: () => import('@/views/CustomerDetailView.vue'),
    props: true,
  },
  { path: '/hisobot', name: 'reports', component: () => import('@/views/ReportsView.vue') },
  { path: '/sozlamalar', name: 'settings', component: () => import('@/views/SettingsView.vue') },
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
    return { name: 'home' }
  }
  return true
})

export default router
