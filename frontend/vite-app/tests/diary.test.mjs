import test from 'node:test'
import assert from 'node:assert/strict'
import { DIARY_TYPES } from '../src/lib/diary.ts'

test('diary choices use semantic names with all as default', () => {
  assert.deepEqual(DIARY_TYPES.map(x => x.value), ['all', 'capsule_diary', 'gratitude_diary', 'discovery_diary'])
  assert.deepEqual(DIARY_TYPES.map(x => x.label), ['全部', '胶囊日记', '感恩日记', '发现日记'])
})
