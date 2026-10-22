// Browser interaction QA with synthetic component/API state; no real downloads.
import assert from 'node:assert/strict'
import path from 'node:path'
import {fileURLToPath, pathToFileURL} from 'node:url'
import {createRequire} from 'node:module'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const front = path.join(root, 'frontend/vite-app')
const require = createRequire(import.meta.url)
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const {createServer} = await import(pathToFileURL(path.join(front, 'node_modules/vite/dist/node/index.js')))
const server = await createServer({root: front, server: {host: '127.0.0.1', port: 0}})
let browser
try {
  await server.listen()
  browser = await chromium.launch({channel: 'msedge', headless: true})
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let state = 'not_installed', installs = 0, cancels = 0, recognitions = 0, available = true, failStatus = false
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) return route.abort()
    if (!url.pathname.startsWith('/api/')) return route.continue()
    const name = url.pathname.slice(4)
    let data = {}
    if (name === '/settings/read') data = {exportConfigured: true, exportRoot: 'synthetic', archiveRoot: 'synthetic'}
    else if (name.startsWith('/components/runtime/')) {
      if (name.endsWith('/status') && failStatus) { failStatus = false; return route.fulfill({status:503,json:{error:'Synthetic unavailable'}}) }
      if (name.endsWith('/install')) {
        assert.equal(route.request().postDataJSON().confirmed, true)
        installs++; state = 'downloading'
      } else if (name.endsWith('/cancel')) { cancels++; state = 'cancelled' }
      data = {state, installed: state === 'installed', available, downloadBytes: 1048576, diskBytes: 2097152, receivedBytes: 0}
    } else if (name === '/ocr/start') { recognitions++; data = {jobId: 'synthetic'} }
    else if (name === '/ocr/status') data = {state: 'completed', result: {pages: []}}
    else if (name === '/library/search/query') data = {items: [], total: 0, hasMore: false, nextOffset: 0}
    else if (name === '/library/semantic/status') data = {state: 'not_installed', downloadBytes: 135429554, model: 'synthetic', storage: 'local'}
    return route.fulfill({json: data})
  })
  await page.goto(server.resolvedUrls.local[0])
  await page.locator('nav').getByRole('button', {name: '识图转文字', exact: true}).click()
  assert.equal(installs, 0)
  await page.locator('input[type=file]').setInputFiles({
    name: 'synthetic.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX2kAAAAASUVORK5CYII=', 'base64'),
  })
  const clickOCR = () => page.getByRole('button', {name: '识别文字', exact: true}).click()
  const dialog = page.getByRole('dialog', {name: '安装本地识别组件'})
  await clickOCR()
  await dialog.waitFor()
  assert.equal(recognitions, 0); assert.equal(installs, 0)
  await dialog.getByRole('button', {name: '取消', exact: true}).click()
  await dialog.waitFor({state: 'hidden'})
  assert.equal(recognitions, 0); assert.equal(installs, 0)
  await clickOCR()
  await dialog.getByRole('button', {name: '确认下载并安装'}).click()
  await dialog.getByText('正在下载：', {exact: false}).waitFor()
  await dialog.getByRole('button', {name: '取消', exact: true}).click()
  await dialog.waitFor({state: 'hidden'})
  assert.equal(cancels, 1); assert.equal(recognitions, 0)
  await clickOCR()
  await dialog.getByRole('button', {name: '确认下载并安装'}).click()
  state = 'installed'
  await dialog.getByRole('button', {name: '继续使用'}).click()
  await page.getByText('识别完成，可以逐页编辑后导出。').waitFor()
  assert.equal(recognitions, 1); assert.equal(installs, 2)
  await page.locator('nav').getByRole('button', {name: '本地搜索', exact: true}).click()
  await page.getByLabel('检索模式', {exact: true}).selectOption('Hybrid')
  await page.getByText('下载并启用', {exact: true}).waitFor()
  assert.equal(installs, 2)
  assert.equal(await dialog.count(), 0)
  // A missing component + declined consent leaves keyword search selected.
  await page.getByLabel('检索模式', {exact: true}).selectOption('FTS5')
  state = 'not_installed'; available = false
  await page.getByLabel('检索模式', {exact: true}).selectOption('Hybrid')
  await dialog.waitFor()
  assert.equal(await dialog.getByRole('button', {name: '确认下载并安装'}).isDisabled(), true)
  await dialog.getByRole('button', {name: '取消', exact: true}).click()
  assert.equal(await page.getByLabel('检索模式', {exact: true}).inputValue(), 'FTS5')
  // A failed first status request must retain intent through recovery.
  available = true; state = 'installed'; failStatus = true
  await page.getByLabel('检索模式', {exact:true}).selectOption('Hybrid')
  await dialog.getByText('无法读取组件状态，请稍后重试。').waitFor()
  await dialog.getByRole('button', {name:'继续使用'}).click()
  assert.equal(await page.getByLabel('检索模式', {exact:true}).inputValue(), 'Hybrid')
  assert.equal(await dialog.count(), 0)
  // Recovery clears obsolete errors; Escape restores the initiating control.
  await page.getByLabel('检索模式', {exact:true}).selectOption('FTS5')
  state = 'not_installed'; failStatus = true
  await page.getByLabel('检索模式', {exact:true}).focus()
  await page.getByLabel('检索模式', {exact:true}).selectOption('Hybrid')
  await dialog.getByText('无法读取组件状态，请稍后重试。').waitFor()
  await dialog.getByRole('button', {name:'确认下载并安装'}).waitFor()
  await page.waitForFunction(() => !document.body.textContent.includes('无法读取组件状态，请稍后重试。'))
  await dialog.press('Escape')
  await dialog.waitFor({state:'hidden'})
  assert.equal(await page.getByLabel('检索模式', {exact:true}).evaluate(el => el === document.activeElement), true)
  assert.equal(recognitions, 1); assert.equal(installs, 2)
  assert.deepEqual(errors, [])
  console.log('PASS: explicit consent, decline, cancel, retry, OCR continuation, shared runtime and FTS5 fallback; no external requests.')
} finally {
  await browser?.close()
  await server.close()
}
