// Mounted React automation with synthetic route fixtures; no user profile/provider.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {spawn} from 'node:child_process'
import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const require=createRequire(import.meta.url)
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output=path.join(root,'build/ai-hybrid/ui-smoke');fs.mkdirSync(output,{recursive:true})
const frontend=spawn(process.execPath,[path.join(root,'frontend/vite-app/node_modules/vite/bin/vite.js'),'--port','5193','--strictPort'],{
  cwd:path.join(root,'frontend/vite-app'),windowsHide:true,stdio:'ignore'})
let browser
try {
  browser=await chromium.launch({channel:'msedge',headless:true})
  const page=await browser.newPage({viewport:{width:1360,height:1000}})
  const errors=[];page.on('pageerror',e=>errors.push(e.message))
  let state='not_installed', downloads=0, searchMode=''
  const source={id:'a'.repeat(64),date:'2026-09-01',diaryType:'discovery_diary',contentType:'diary',title:'合成日记',snippet:'合成检索内容'}
  await page.route('**/api/**',route=>{
    const suffix=new URL(route.request().url()).pathname.slice(4)
    let result={}
    if(suffix==='/health')result={status:'ok'}
    else if(suffix==='/settings/read')result={exportConfigured:true,exportRoot:'synthetic-selected-root'}
    else if(suffix==='/library/semantic/status')result={state,model:'intfloat/multilingual-e5-small',downloadBytes:135429554}
    else if(suffix==='/library/semantic/install'){downloads++;assert.equal(route.request().postDataJSON().confirmed,true);state='downloading';result={state}}
    else if(suffix==='/library/search/query'){
      searchMode=route.request().postDataJSON().retrievalMode
      result={items:[source],total:1,nextOffset:1,retrieval:{mode:'FTS5',fallback:'语义检索暂时不可用，已使用 FTS5 完成本次搜索。'}}
    }else if(suffix==='/library/search/detail')result={...source,body:'合成完整日记'}
    else if(suffix==='/library/ai/status')result={providers:[]}
    else throw Error('Unexpected synthetic route '+suffix)
    return route.fulfill({json:result})
  })
  for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:5193');break}catch{await new Promise(r=>setTimeout(r,200))}}
  await page.getByRole('button',{name:'本地搜索',exact:true}).click()
  const selector=page.getByLabel('检索模式',{exact:true})
  assert.deepEqual(await selector.locator('option').allTextContents(),['FTS5','Hybrid'])
  assert.equal(await selector.inputValue(),'FTS5')
  await selector.selectOption('Hybrid')
  await page.getByText('尚未安装',{exact:true}).waitFor()
  assert.equal(downloads,0)
  await page.getByRole('button',{name:'下载并启用',exact:true}).click()
  await page.getByText('正在下载组件…',{exact:true}).waitFor();assert.equal(downloads,1)
  for(const [next,label] of [['verifying','正在校验组件…'],['indexing','正在本机建立语义索引…'],['ready','Hybrid 已就绪'],['download_failed','下载失败，请重试。'],['verification_failed','校验失败，组件未启用，请重新下载。']]){
    state=next;await page.getByText(label,{exact:true}).waitFor()
  }
  await page.getByRole('textbox',{name:'关键词'}).fill('合成问题')
  await page.getByRole('button',{name:'搜索',exact:true}).click()
  await page.getByText('语义检索暂时不可用，已使用 FTS5 完成本次搜索。',{exact:true}).waitFor()
  assert.equal(searchMode,'Hybrid')
  await page.getByText('合成检索内容',{exact:true}).click()
  await page.getByText('合成完整日记',{exact:true}).waitFor()
  await page.getByRole('checkbox',{name:'选择 2026-09-01 合成日记'}).check()
  await page.getByRole('button',{name:'用 AI 查看已选日记（1）'}).click()
  await page.getByText('🚧 AI 日记助手仍在建设中',{exact:true}).waitFor()
  await page.getByText('尚未配置 AI 服务商。请先在设置中保存 API Key 与模型。',{exact:true}).waitFor()
  assert.equal(await page.getByLabel('检索模式',{exact:true}).count(),0)
  const notice=page.getByRole('region',{name:'AI 实验状态'})
  assert.ok(!(await notice.getAttribute('class')).includes('destructive'))
  await page.screenshot({path:path.join(output,'experimental-notice.png')})
  await page.getByRole('button',{name:'问日记',exact:true}).click()
  await page.getByLabel('检索模式',{exact:true}).waitFor()
  assert.deepEqual(errors,[])
  console.log('PASS: mounted React two-mode selector, explicit download, lifecycle states, fallback, source detail, selected handoff, experimental notice, provider-empty state.')
}finally{if(browser)await browser.close();frontend.kill()}
