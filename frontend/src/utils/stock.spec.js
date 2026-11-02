import { describe, expect, it } from 'vitest'

import { stockLevel } from './stock'

describe('stockLevel', () => {
  it.each([
    [{ stock: 0, min_stock: 3 }, 'out'],
    [{ stock: '-1', min_stock: 3 }, 'out'],
    [{ stock: 3, min_stock: 3 }, 'low'], // at the minimum = "kam qolgan", like the backend
    [{ stock: 6, min_stock: 3 }, 'near'], // up to twice the minimum
    [{ stock: 7, min_stock: 3 }, 'ok'],
    [{ stock: '2.500', min_stock: '0' }, 'ok'], // API sends decimals as strings
    [{}, 'out'],
    [null, 'out'],
  ])('%o → %s', (product, level) => {
    expect(stockLevel(product)).toBe(level)
  })
})
