import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const source = (file) => readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')

test('configured credentials need explicit replacement and deletion confirmation', async () => {
  const ui = await source('AISettingsPage.tsx')
  assert.match(ui, /configured && !editingKey/)
  assert.match(ui, /\(!configured \|\| editingKey\)/)
  assert.match(ui, /替换 API Key/)
  assert.match(ui, /取消替换/)
  assert.match(ui, /setConfirmDelete\(true\)/)
  assert.match(ui, /confirmDelete &&/)
  assert.match(ui, /确认删除 API Key/)
  assert.doesNotMatch(ui, /localStorage|sessionStorage|setKey\(data\./)
})
test('archive completion offers a folder action, not internal JSON', async () => {
  const ui = await source('ProductPages.tsx')
  assert.match(ui, /job.state === "completed" \|\| job.state === "partial"/)
  assert.match(ui, /completed && <ArchiveFolderButton/)
  assert.match(ui, /setCompleted\(false\)/)
  assert.doesNotMatch(ui, /diaries\.normalized\.json/)
})
test('folder requests carry only a fixed area, never a filesystem path', async () => {
  const ui = await source('ArchiveFolderButton.tsx')
  assert.match(ui, /request\("\/settings\/open-archive", \{ area \}\)/)
  assert.doesNotMatch(ui, /shell|exec|path:|localStorage/)
  assert.match(ui, /role="alert"/)
  const rust = await readFile(new URL('../src-tauri/src/main.rs', import.meta.url), 'utf8')
  assert.match(rust, /"\/settings\/open-archive"/)
})
test('contextual onboarding is optional and explains archive boundaries', async () => {
  const ui = await source('App.tsx')
  assert.match(ui, /<details/)
  for (const text of ['无需先归档', '不必日常打开 JSON', '本地语义组件', 'archive/capsules']) assert.ok(ui.includes(text))
})
test('AI and OCR expose output-folder guidance without removing experimental notice', async () => {
  const ai = await source('AIAssistantPage.tsx')
  const ocr = await source('ProductPages.tsx')
  assert.match(ai, /ArchiveFolderButton area="ai"/)
  assert.match(ocr, /ArchiveFolderButton area="ocr"/)
  assert.match(ai, /AI 日记助手仍在建设中/)
})
