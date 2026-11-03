import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCartStore } from './cart'

// The real client pulls in the router and auth store; the cart only needs get().
const get = vi.fn()
vi.mock('@/api/client', () => ({ default: { get: (...args) => get(...args) } }))

const STORAGE_KEY = 'cart:v1'
const product = (id, { price = 1000, stock = 5 } = {}) => ({ id, price, stock })

describe('cart store', () => {
  beforeEach(() => {
    localStorage.clear()
    get.mockReset()
    setActivePinia(createPinia())
  })

  it('adds a product and totals price × qty', () => {
    const cart = useCartStore()

    expect(cart.addProduct(product('a'), 3)).toBe(false)

    expect(cart.items).toHaveLength(1)
    expect(cart.total).toBe(3000)
  })

  it('merges a second add into the same line and caps it at stock', () => {
    const cart = useCartStore()
    cart.addProduct(product('a'), 3)

    expect(cart.addProduct(product('a'), 4)).toBe(true) // capped

    expect(cart.items).toHaveLength(1)
    expect(cart.items[0].qty).toBe(5)
  })

  it('does not add a product that is out of stock', () => {
    const cart = useCartStore()

    expect(cart.addProduct(product('a', { stock: 0 }), 1)).toBe(true)

    expect(cart.isEmpty).toBe(true)
  })

  it('keeps fractional kg exact (0.1 + 0.2 = 0.3)', () => {
    const cart = useCartStore()
    cart.addProduct(product('kg', { stock: 10 }), 0.1)
    cart.addProduct(product('kg', { stock: 10 }), 0.2)

    expect(cart.items[0].qty).toBe(0.3)
  })

  it('setQty caps at stock, and 0 removes the line and the saved cart', () => {
    const cart = useCartStore()
    cart.addProduct(product('a'), 1)

    expect(cart.setQty('a', 9)).toBe(true)
    expect(cart.items[0].qty).toBe(5)

    cart.setQty('a', 0)
    expect(cart.isEmpty).toBe(true)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('survives a reload with the same client id', () => {
    const cart = useCartStore()
    cart.addProduct(product('a'), 2)
    const clientId = cart.clientId

    setActivePinia(createPinia())
    const restored = useCartStore()

    expect(restored.items).toEqual([{ product: product('a'), qty: 2 }])
    expect(restored.clientId).toBe(clientId)
  })

  it('starts empty when the saved cart is corrupt', () => {
    localStorage.setItem(STORAGE_KEY, '{not json')

    expect(useCartStore().isEmpty).toBe(true)
  })

  it('clear() empties the cart and issues a new client id (next sale is a new sale)', () => {
    const cart = useCartStore()
    cart.addProduct(product('a'), 1)
    const clientId = cart.clientId

    cart.clear()

    expect(cart.isEmpty).toBe(true)
    expect(cart.clientId).not.toBe(clientId)
  })

  it('refresh() drops archived products and caps lines at current stock', async () => {
    const cart = useCartStore()
    cart.addProduct(product('gone'), 1)
    cart.addProduct(product('b'), 4)
    get.mockResolvedValue({
      data: { data: { results: [product('b', { price: 1100, stock: 2 })] } },
    })

    expect(await cart.refresh()).toBe(true)

    expect(get).toHaveBeenCalledWith('/products/', {
      params: { ids: 'gone,b', page_size: 100 },
    })
    expect(cart.items).toEqual([{ product: product('b', { price: 1100, stock: 2 }), qty: 2 }])
    expect(cart.total).toBe(2200)
  })

  it('refresh() reports no change when nothing changed', async () => {
    const cart = useCartStore()
    cart.addProduct(product('a'), 1)
    get.mockResolvedValue({ data: { data: [product('a')] } })

    expect(await cart.refresh()).toBe(false)
  })
})
