import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const search = await readFile(new URL("../src/SearchPage.tsx", import.meta.url), "utf8")
test("FTS baseline and opt-in Hybrid preserve diary scope", () => {
  assert.match(search, /useState<RetrievalMode>\("FTS5"\)/)
  assert.match(search, /if \(mode === "Hybrid"\) setContentType\("diary"\)/)
  assert.match(search, /disabled=\{retrievalMode === "Hybrid"\}/)
  assert.match(search, /contentType, retrievalMode/)
  assert.doesNotMatch(search, /apiKey|embedding|queryRewrite|sqlitePath/)
})
test("bounded related results keep selection and source navigation", () => {
  assert.match(search, /最多 200 条候选/)
  assert.match(search, /匹配不代表事件确实发生/)
  assert.match(search, /results.limited/)
  assert.match(search, /onSelectForAI\(selected\)/)
  assert.match(search, /\/library\/search\/detail/)
})
