import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const search = await readFile(new URL("../src/SearchPage.tsx", import.meta.url), "utf8")
test("related search is opt-in, local and diary-only", () => {
  assert.match(search, /\[related, setRelated\] = useState\(false\)/)
  assert.match(search, /本地相关词检索（仅日记，不联网）/)
  assert.match(search, /if \(e.target.checked\) setContentType\("diary"\)/)
  assert.match(search, /disabled=\{related\}/)
  assert.match(search, /contentType, related/)
  assert.doesNotMatch(search, /apiKey|embedding|queryRewrite|sqlitePath/)
})
test("bounded related results keep selection and source navigation", () => {
  assert.match(search, /最多 200 条候选/)
  assert.match(search, /匹配不代表事件确实发生/)
  assert.match(search, /results.limited/)
  assert.match(search, /onSelectForAI\(selected\)/)
  assert.match(search, /\/library\/search\/detail/)
})
