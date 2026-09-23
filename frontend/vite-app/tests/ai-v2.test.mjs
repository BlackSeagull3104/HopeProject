import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { presetRange } from "../src/lib/ai.ts"

test("review presets handle month and year boundaries", () => {
  const today = new Date(2026, 0, 3)
  assert.deepEqual(presetRange("7d", today), { beginDate: "2025-12-28", endDate: "2026-01-03" })
  assert.deepEqual(presetRange("30d", today), { beginDate: "2025-12-05", endDate: "2026-01-03" })
  assert.deepEqual(presetRange("month", today), { beginDate: "2026-01-01", endDate: "2026-01-03" })
  assert.deepEqual(presetRange("previous", today), { beginDate: "2025-12-01", endDate: "2025-12-31" })
  assert.deepEqual(presetRange("custom", today), { beginDate: "", endDate: "" })
})

const assistant = await readFile(new URL("../src/AIAssistantPage.tsx", import.meta.url), "utf8")
const search = await readFile(new URL("../src/SearchPage.tsx", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8")

test("search hands selected stable IDs to the assistant without paths", () => {
  assert.match(search, /onSelectForAI\(selected\)/)
  assert.match(app, /setAiSelectedIds\(ids\)/)
  assert.match(assistant, /sourceIds: selectedIds/)
  assert.doesNotMatch(search, /sourcePath|sqlitePath/)
})

test("assistant exposes modes, progress, confirmation, cancellation, retry and export", () => {
  for (const label of ["问日记", "回顾", "时间线", "已选日记", "确认发送并开始", "取消生成", "重试未完成的请求", "导出 Markdown"])
    assert.ok(assistant.includes(label), label)
  for (const route of ["/library/ai/prepare", "/library/ai/start", "/library/ai/progress", "/library/ai/cancel", "/library/ai/export", "/library/search/detail"])
    assert.ok(assistant.includes(route), route)
  assert.match(assistant, /尚未配置 AI 服务商/)
  assert.match(assistant, /请先在本地搜索勾选日记/)
  assert.match(assistant, /当前服务商 \/ 模型/)
  assert.match(assistant, /多次 AI 请求/)
})
