// Real local backend + React integration with synthetic files; never log in to Hope.
import fs from 'node:fs'
import path from 'node:path'
import {spawn} from 'node:child_process'
import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const require=createRequire(import.meta.url)
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output=path.resolve(process.argv[2] || path.join(root,'build/product-smoke'))
fs.mkdirSync(output,{recursive:true})
const home=path.join(output,'profile'), exports=path.join(output,'exports')
const backend=spawn(process.env.HOPE_TEST_PYTHON || path.join(root,'.venv/Scripts/python.exe'),['-B','-X','utf8','-m','hope_archive.local_api'],{
  cwd:root,windowsHide:true,stdio:'ignore',env:{...process.env,HOPE_ARCHIVE_HOME:home,LOCALAPPDATA:home,PYTHONPATH:[path.join(root,'src'),path.join(root,'.venv/Lib/site-packages')].join(path.delimiter)}})
const frontend=spawn(process.execPath,[path.join(root,'frontend/vite-app/node_modules/vite/bin/vite.js')],{
  cwd:path.join(root,'frontend/vite-app'),windowsHide:true,stdio:'ignore'})
let browser, page
try {
  browser=await chromium.launch({channel:'msedge',headless:true})
  page=await browser.newPage({viewport:{width:1360,height:900}})
  const external=[];const errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.route('**/*',route=>{const url=new URL(route.request().url());if(!['127.0.0.1','localhost'].includes(url.hostname) && !['data:','blob:'].includes(url.protocol)){external.push(url.origin);return route.abort()}return route.continue()})
  for(let i=0;i<60;i++){try{await page.goto('http://127.0.0.1:5173');break}catch{await new Promise(r=>setTimeout(r,300))}}
  await page.getByRole('dialog',{name:'选择导出位置'}).waitFor()
  await page.getByRole('button',{name:'稍后设置'}).click()
  const labels=await page.locator('nav button').allTextContents()
  if(labels.join('|')!=='日记预览|日记归档|时间胶囊|本地搜索|识图转文字|设置')throw Error('Navigation mismatch')
  await page.getByText('还没有本地日记。',{exact:true}).waitFor()
  await page.getByRole('button',{name:'本地搜索',exact:true}).click()
  if(await page.getByLabel('开始日期').inputValue() || await page.getByLabel('结束日期').inputValue())throw Error('Search dates prepopulated')
  await page.getByText('尚未归档的日记不会出现在搜索结果中。',{exact:false}).waitFor()
  await page.getByRole('textbox',{name:'关键词'}).fill('synthetic-missing')
  await page.getByRole('button',{name:'搜索',exact:true}).click()
  await page.getByText('没有找到匹配的内容，换个关键词试试吧。',{exact:true}).waitFor()
  await page.getByRole('button',{name:'时间胶囊',exact:true}).click()
  if(await page.getByText('未开启',{exact:true}).count())throw Error('Unopened option visible')
  await page.getByRole('button',{name:'设置',exact:true}).click()
  await page.getByRole('heading',{name:'AI API 设置'}).waitFor()
  await page.waitForFunction(()=>document.querySelectorAll('select')[0]?.options.length===11)
  await page.getByLabel('服务商',{exact:true}).locator('option').last().waitFor({state:'attached'})
  if(await page.getByLabel('服务商',{exact:true}).locator('option').count()!==11)throw Error('Missing providers')
  await page.getByLabel('服务商',{exact:true}).selectOption('anthropic')
  await page.getByLabel('模型名称').fill('custom-synthetic-model')
  await page.screenshot({path:path.join(output,'settings.png')})
  const saved=await page.request.post('http://127.0.0.1:5173/api/settings/save',{headers:{'X-Hope-Client':'react'},data:{exportRoot:exports}})
  if(!saved.ok())throw Error('Settings persistence failed')
  await page.reload()
  await page.getByRole('button',{name:'识图转文字',exact:true}).click()
  if(await page.getByRole('dialog',{name:'选择导出位置'}).count())throw Error('Configured onboarding repeated')
  const names=['01_chinese_clear.png','02_english_clear.png','03_mixed_technical.png','16_blank.png']
  await page.locator('input[type=file]').setInputFiles(names.map(name=>path.join(root,'tests/fixtures/ocr',name)))
  await page.getByRole('button',{name:'识别文字',exact:true}).click()
  await page.getByText('识别完成，可以逐页编辑后导出。',{exact:true}).waitFor({timeout:90000})
  await page.getByLabel('第 1 页文字').fill('编辑后的合成中文 English export')
  if(!await page.getByLabel('第 3 页文字').inputValue().then(v=>v.includes('Python')))throw Error('Mixed OCR failed')
  await page.getByText('未检测到文字，可手动输入。',{exact:true}).waitFor()
  for(const format of ['markdown','pdf','docx','tex','txt']){
    await page.getByLabel('导出格式').selectOption(format)
    await page.getByRole('button',{name:'导出编辑后的文字'}).click()
    await page.getByText(/已导出：/).waitFor()
    await page.getByRole('button',{name:'导出编辑后的文字'}).waitFor({state:'visible'})
    // Wait until the export operation releases its disabled button.
    await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='导出编辑后的文字'&&!b.disabled))
  }
  await page.screenshot({path:path.join(output,'ocr.png')})
  const generated=fs.readdirSync(path.join(exports,'ocr'))
  for(const ext of ['md','pdf','docx','tex','txt'])if(!generated.some(f=>f.endsWith('.'+ext)))throw Error('Missing export '+ext)
  const txt=generated.find(f=>f.endsWith('.txt'))
  if(!fs.readFileSync(path.join(exports,'ocr',txt),'utf8').includes('编辑后的合成中文'))throw Error('Edits not exported')
  if(errors.length || external.length)throw Error('Unexpected page error or external request')
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({navigation:labels,onboardingCancel:true,persistedExportRoot:true,blankSearchDates:true,openedOnly:true,providers:11,realOCR:true,editableResult:true,formats:5,externalRequests:external,javascriptErrors:errors},null,2))
  console.log('PASS: real product UI, onboarding, settings, six navigation sections, offline OCR and five edited exports')
}catch(error){if(page){await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});console.log('Synthetic test alerts:',await page.getByRole('alert').allTextContents())}throw error}finally{if(browser)await browser.close();backend.kill();frontend.kill()}
