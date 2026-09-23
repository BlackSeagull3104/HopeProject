import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const source = await readFile(new URL("../src/AIAssistantPage.tsx", import.meta.url), "utf8")

test("assistant requires a first-use disclosure and exposes source navigation", () => {
  assert.match(source, /只将回答当前问题所需的相关日记片段/)
  assert.match(source, /最多 8 个相关日记片段/)
  assert.match(source, /不会发送完整归档、内部路径或 API Key/)
  assert.match(source, /\/library\/ai\/ask/)
  assert.match(source, /\/library\/search\/detail/)
})

test("assistant keeps consent and conversation session-local", () => {
  assert.doesNotMatch(source, /localStorage|sessionStorage/)
  assert.match(source, /slice\(-6\)/)
  assert.match(source, /disclosureAccepted/)
})
