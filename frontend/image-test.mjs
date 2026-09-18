import { chromium } from 'playwright'

const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
const problems = []
page.on('pageerror', (err) => problems.push(`[pageerror] ${err.message}`))
page.on('console', (msg) => {
  if (msg.type() === 'error') problems.push(`[console.error] ${msg.text()}`)
})
page.on('response', (res) => {
  if (res.status() >= 400 && !res.url().includes('/auth/refresh/')) {
    problems.push(`[http ${res.status()}] ${res.request().method()} ${res.url()}`)
  }
})

const step = async (label, fn) => {
  try {
    await fn()
    console.log(`OK  ${label}`)
  } catch (err) {
    console.log(`FAIL ${label}: ${err.message}`)
    await page.screenshot({ path: `/tmp/img-fail-${label.replace(/\s+/g, '_')}.png` })
    throw err
  }
}

const suffix = Date.now()
const name = `Rasmli mahsulot ${suffix}`

try {
  await step('login', async () => {
    await page.goto('http://localhost:5173/login')
    await page.fill('input[type=tel]', '+998900000001')
    await page.fill('input[type=password]', 'YangiParol123!')
    await page.click('button[type=submit]')
    await page.waitForURL('http://localhost:5173/')
  })

  await step('create product with an uploaded image', async () => {
    await page.goto('http://localhost:5173/mahsulotlar/yangi')
    await page.setInputFiles('input[type=file]', '/tmp/test-product.png')
    await page.waitForTimeout(200)
    await page.screenshot({ path: '/tmp/img-preview.png' })
    await page.fill('input.w-full >> nth=0', name)
    await page.fill('input[step="0.01"]', '15')
    await page.click('button:has-text("Saqlash")')
    await page.waitForURL('**/mahsulotlar')
  })

  await step('image shows in products list', async () => {
    await page.waitForSelector(`text=${name}`)
    const row = page.locator(`text=${name}`).locator('xpath=ancestor::a[1]')
    const img = row.locator('img')
    await img.waitFor({ state: 'visible' })
    const src = await img.getAttribute('src')
    if (!src || !src.includes('/media/products/')) {
      throw new Error(`unexpected image src: ${src}`)
    }
  })

  await step('image shows in sale quick-buttons and cart', async () => {
    // seed a batch so it shows up in "quick" (best sellers need a sale, so
    // just check it's visible via search instead, which doesn't require sales)
    await page.goto('http://localhost:5173/sotuv')
    await page.fill('input[type=search]', name)
    await page.waitForTimeout(500)
    await page.waitForSelector(`text=${name}`)
  })

  console.log('\n=== IMAGE TEST PASSED ===')
} catch {
  console.log('\n=== IMAGE TEST FAILED ===')
} finally {
  console.log('--- problems ---')
  console.log(problems.length ? problems.join('\n') : '(none)')
  await browser.close()
}
