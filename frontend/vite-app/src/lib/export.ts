import { isTauri } from "@tauri-apps/api/core"
import { open } from "@tauri-apps/plugin-dialog"

export const EXPORT_FORMATS = [
  { value: "markdown", label: "Markdown (.md)" },
  { value: "tex", label: "TeX (.tex)" },
  { value: "pdf", label: "PDF (.pdf)" },
  { value: "docx", label: "Word (.docx)" },
] as const
export type ExportFormat = (typeof EXPORT_FORMATS)[number]["value"]

export function todayString() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`
}

export function dateRangeError(
  start: string,
  end: string,
  today = todayString()
) {
  if (!start || !end) return "请选择开始和结束日期。"
  if (end < start) return "结束日期不能早于开始日期。"
  if (end > today) return "结束日期不能晚于今天。"
  return ""
}

export async function pickDirectory(current: string): Promise<string | null> {
  if (!isTauri())
    throw new Error("浏览器模式不支持原生文件夹选择，请手动填写目录。")
  return await open({
    directory: true,
    multiple: false,
    title: "选择输出文件夹",
    ...(current ? { defaultPath: current } : {}),
  })
}
