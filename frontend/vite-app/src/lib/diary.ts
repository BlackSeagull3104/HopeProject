export const DIARY_TYPES = [
  { value: "all", label: "全部" },
  { value: "capsule_diary", label: "胶囊日记" },
  { value: "gratitude_diary", label: "感恩日记" },
  { value: "discovery_diary", label: "发现日记" },
] as const
export type DiaryType = (typeof DIARY_TYPES)[number]["value"]
