export type AIMode = "ask" | "review" | "timeline" | "selected"
export type DatePreset = "7d" | "30d" | "month" | "previous" | "custom"

function iso(day: Date) {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`
}

export function presetRange(preset: DatePreset, today = new Date()) {
  const year = today.getFullYear()
  const month = today.getMonth()
  const end = new Date(year, month, today.getDate())
  if (preset === "custom") return { beginDate: "", endDate: "" }
  if (preset === "month") return { beginDate: iso(new Date(year, month, 1)), endDate: iso(end) }
  if (preset === "previous") return {
    beginDate: iso(new Date(year, month - 1, 1)),
    endDate: iso(new Date(year, month, 0)),
  }
  const begin = new Date(year, month, today.getDate() - (preset === "7d" ? 6 : 29))
  return { beginDate: iso(begin), endDate: iso(end) }
}
