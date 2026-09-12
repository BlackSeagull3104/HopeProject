import test from "node:test"
import assert from "node:assert/strict"
import { highlightedParts } from "../src/lib/search.ts"
test("Chinese and repeated literal matches highlight without HTML interpretation", () => {
  const source = "<script>乒乓球 & 乒乓球</script>"
  const parts = highlightedParts(source, "乒乓球")
  assert.equal(parts.filter(p => p.match).length, 2)
  assert.equal(parts.map(p => p.text).join(""), source)
  assert.equal(highlightedParts("[a].*", ".*").find(p => p.match)?.text, ".*")
  assert.equal(highlightedParts("ABC", "abc")[0].match, true)
})
