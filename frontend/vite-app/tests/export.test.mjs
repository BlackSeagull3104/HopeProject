import test from 'node:test'
import assert from 'node:assert/strict'
import { dateRangeError, EXPORT_FORMATS, pickDirectory } from '../src/lib/export.ts'
test('end date remains freely selectable up to today', () => {
  for (const end of ['2026-09-01','2026-09-08','2026-09-10']) assert.equal(dateRangeError('2026-09-01', end, '2026-09-10'), '')
  assert.notEqual(dateRangeError('2026-09-08','2026-09-01','2026-09-10'), '')
  assert.notEqual(dateRangeError('2026-09-01','2026-09-11','2026-09-10'), '')
})
test('all four format values are available', () => {
  assert.deepEqual(EXPORT_FORMATS.map(x => x.value), ['markdown','tex','pdf','docx'])
})
test('browser fallback reports manual directory entry', async () => {
  await assert.rejects(pickDirectory(''), /浏览器模式/)
})
