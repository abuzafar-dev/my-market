import { ref } from 'vue'

import api from '@/api/client'

// A list that loads in chunks. The API pages everything (20 by default), and a
// shop can have thousands of products / hundreds of customers, so a screen
// must keep asking for the next page instead of showing only the first one.
// `getParams` is read on every request, so search text / filters are always current.
export function usePagedList(path, getParams = () => ({}), pageSize = 40) {
  const items = ref([])
  const total = ref(0)
  const loading = ref(true)
  const loadingMore = ref(false)
  const hasMore = ref(false)
  let page = 1
  let seq = 0 // a newer load() makes older, slower responses irrelevant

  async function fetchPage(number) {
    const response = await api.get(path, {
      params: { ...getParams(), page: number, page_size: pageSize },
    })
    const data = response.data.data
    // Unpaginated endpoints answer with a bare array.
    return Array.isArray(data) ? { results: data, count: data.length, next: null } : data
  }

  async function load() {
    const mine = ++seq
    loading.value = true
    page = 1
    try {
      const data = await fetchPage(1)
      if (mine !== seq) return
      items.value = data.results
      total.value = data.count
      hasMore.value = Boolean(data.next)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  async function more() {
    if (!hasMore.value || loading.value || loadingMore.value) return
    const mine = seq
    loadingMore.value = true
    try {
      const data = await fetchPage(page + 1)
      if (mine !== seq) return
      page += 1
      items.value = [...items.value, ...data.results]
      hasMore.value = Boolean(data.next)
    } finally {
      loadingMore.value = false
    }
  }

  return { items, total, loading, loadingMore, hasMore, load, more }
}
