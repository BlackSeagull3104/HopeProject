// Synthetic desktop IPC; never contacts Hope or stores real credentials.
import assert from 'node:assert/strict'
import path from 'node:path'
import {fileURLToPath,pathToFileURL} from 'node:url'
import {createRequire} from 'node:module'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const front=path.join(root,'frontend/vite-app')
const require=createRequire(import.meta.url)
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const {createServer}=await import(pathToFileURL(path.join(front,'node_modules/vite/dist/node/index.js')))
const server=await createServer({root:front,server:{host:'127.0.0.1',port:0}})
let browser
try {
 await server.listen();browser=await chromium.launch({channel:'msedge',headless:true})
 const page=await browser.newPage();page.setDefaultTimeout(15000)
 const errors=[];page.on('pageerror',e=>errors.push(e.message))
 let saved=null,loginCount=0,holdRestore=true,releaseRestore
 const restoreGate=new Promise(resolve=>{releaseRestore=resolve})
 await page.exposeFunction('fixtureIPC',async (command,args)=>{
  assert.equal(command,'desktop_request')
  const p=args.path;let body={}
  if(p==='/auth/restore') {if(holdRestore)await restoreGate;body={session:saved}}
  else if(p.startsWith('/auth/login/')) {loginCount++;assert.equal(args.body.remember,true);saved={token:'synthetic-new-token',userId:'synthetic-user',displayName:'合成用户'};body=saved}
  else if(p==='/auth/logout'){saved=null;body={success:true}}
  else if(p==='/settings/read')body={exportConfigured:true,exportRoot:'synthetic'}
  else if(p==='/diaries/preview')body={diaries:[],hasMore:false,page:0}
  else if(p==='/library/capsules')body={items:[]}
  return {status:200,body}
 })
 await page.addInitScript(()=>{window.isTauri=true;window.__TAURI_INTERNALS__={invoke:(command,args)=>window.fixtureIPC(command,args)}})
 await page.route('**/*',r=>{const u=new URL(r.request().url());return ['localhost','127.0.0.1'].includes(u.hostname)?r.continue():r.abort()})
 await page.goto(server.resolvedUrls.local[0])
 // Hold startup restoration while trying every page's manual-login entry.
 await page.getByRole('button',{name:'正在恢复登录…',exact:true}).waitFor()
 assert.equal(await page.getByRole('button',{name:'正在恢复登录…',exact:true}).isDisabled(),true)
 for(const [section,action] of [['日记预览','登录 Hope'],['日记归档','归档日记'],['时间胶囊','下载 / 更新已开启胶囊']]){
  await page.getByRole('navigation').getByRole('button',{name:section,exact:true}).click()
  await page.getByRole('main').getByRole('button',{name:action,exact:true}).click()
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>resolve())))
  assert.equal(await page.getByRole('dialog',{name:'登录 Hope',exact:true}).count(),0,`${section} must wait for restoration before manual login`)
  assert.equal(loginCount,0)
 }
 holdRestore=false;releaseRestore()
 await page.getByRole('button',{name:'登录 Hope',exact:true}).last().waitFor()
 await page.getByRole('navigation').getByRole('button',{name:'日记预览',exact:true}).click()
 await page.getByRole('button',{name:'登录 Hope',exact:true}).last().click()
 const box=page.getByRole('checkbox',{name:/在此电脑保留登录/})
 assert.equal(await box.isChecked(),false)
 await box.check();await page.getByLabel('手机号',{exact:true}).fill('synthetic-mobile')
 await page.getByLabel('验证码',{exact:true}).fill('synthetic-code')
 await page.getByRole('button',{name:'登录',exact:true}).click()
 await page.getByText('已登录：合成用户',{exact:true}).waitFor()
 await page.reload();await page.getByText('已登录：合成用户',{exact:true}).waitFor()
 assert.equal(loginCount,1)
 assert.equal(await page.evaluate(()=>localStorage.length),0)
 await page.getByRole('button',{name:'退出登录',exact:true}).click()
 await page.reload();await page.getByRole('button',{name:'登录 Hope',exact:true}).last().waitFor()
 assert.equal(saved,null);assert.equal(loginCount,1);assert.deepEqual(errors,[])
 console.log('PASS: all login entries wait for restoration, opt-in default, remembered desktop UI restart, no browser storage, explicit logout and no repeat login.')
} finally {await browser?.close();await server.close()}
