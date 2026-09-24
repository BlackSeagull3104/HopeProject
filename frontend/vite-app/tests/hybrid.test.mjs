import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { retrievalModes, stateLabels, working } from "../src/lib/retrieval.ts"

test("exactly two public retrieval modes and complete lifecycle", () => {
  assert.deepEqual(retrievalModes, ["FTS5", "Hybrid"])
  assert.equal(Object.keys(stateLabels).length, 10)
  for (const state of ["downloading", "verifying", "indexing"]) assert.ok(working(state))
  for (const state of ["not_installed", "ready", "download_failed", "verification_failed", "index_failed", "rebuild_required", "installed"]) assert.ok(!working(state))
})
const control = await readFile(new URL("../src/RetrievalControl.tsx", import.meta.url), "utf8")
const assistant = await readFile(new URL("../src/AIAssistantPage.tsx", import.meta.url), "utf8")
test("component download is explicit, disclosed and not triggered by mounting", () => {
  assert.match(control, /onClick=\{\(\) => void action\("install"\)\}/)
  assert.match(control, /confirmed: true/)
  assert.match(control, /129.16 MiB/)
  assert.match(control, /不会上传/)
  assert.match(control, /组件未就绪时使用 FTS5；不会自动下载/)
  const effect = control.slice(control.indexOf("useEffect(()"), control.indexOf("async function action"))
  assert.doesNotMatch(effect, /action\(|\/install/)
  assert.doesNotMatch(control, /sqlitePath|apiKey|90\.90/)
})
test("experimental information is always shown before provider and distinct from errors", () => {
  const start = assistant.indexOf('<section aria-label="AI 实验状态"')
  const notice = assistant.slice(start, assistant.indexOf("</section>", start))
  assert.ok(start > 0 && start < assistant.indexOf("!providers.length ?"))
  assert.match(notice, /🚧 AI 日记助手仍在建设中/)
  assert.match(notice, /当前功能仍处于实验阶段，尚未完成完整的人工测试，部分模型或功能可能无法正常使用。日记归档、搜索、OCR 与导出等基础功能不受影响。/)
  assert.doesNotMatch(notice, /destructive|role="alert"|dialog|onClick/)
  assert.match(assistant, /role="alert" className="text-destructive"/)
})
test("AI only exposes retrieval on Ask and Timeline and displays fallback", () => {
  assert.match(assistant, /mode === "ask" \|\| mode === "timeline"/)
  assert.match(assistant, /result.retrieval\?\.fallback/)
  assert.match(assistant, /prepared.retrieval\?\.fallback/)
})
test("desktop IPC explicitly allows every AI and semantic route", async () => {
  const rust = await readFile(new URL("../src-tauri/src/main.rs", import.meta.url), "utf8")
  for (const suffix of ["status", "ask", "prepare", "start", "progress", "cancel", "export"])
    assert.ok(rust.includes(`| "/library/ai/${suffix}"`))
  for (const suffix of ["status", "install", "index", "rebuild"])
    assert.ok(rust.includes(`| "/library/semantic/${suffix}"`))
})
