import { useEffect, useRef, useState } from "react"
import { request, type Session, type Job } from "@/lib/api"
import { EXPORT_FORMATS, todayString, type ExportFormat } from "@/lib/export"
import { DIARY_TYPES } from "@/lib/diary"
import { Button } from "@/components/ui/button"
import { ArchiveFolderButton } from "@/ArchiveFolderButton"

export const inputClass = "min-w-0 rounded-lg border bg-background p-3 text-sm"
export function FormatPicker({
  value,
  onChange,
}: {
  value: ExportFormat
  onChange: (v: ExportFormat) => void
}) {
  return (
    <label className="grid gap-2">
      导出格式
      <select
        aria-label="导出格式"
        className={inputClass}
        value={value}
        onChange={(e) => onChange(e.target.value as ExportFormat)}
      >
        {EXPORT_FORMATS.map((f) => (
          <option key={f.value} value={f.value}>
            {f.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ArchivePage({
  session,
  onLogin,
}: {
  session: Session | null
  onLogin: () => void
}) {
  const [beginDate, setBegin] = useState(todayString().slice(0, 8) + "01")
  const [endDate, setEnd] = useState(todayString())
  const [diaryType, setType] = useState("all")
  const [formats, setFormats] = useState<ExportFormat[]>(["markdown"])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [jobId, setJobId] = useState("")
  const [completed, setCompleted] = useState(false)
  useEffect(() => {
    if (!jobId || !session) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const job = await request<Job>(`/jobs/${jobId}`, undefined, session!)
        if (!active) return
        setMessage(job.stage)
        if (job.state === "running") timer = setTimeout(poll, 700)
        else {
          setBusy(false)
          setJobId("")
          if (job.state === "failed") setError(job.stage)
          setCompleted(job.state === "completed" || job.state === "partial")
        }
      } catch (cause) {
        if (active) {
          setError(String(cause))
          setBusy(false)
          setJobId("")
        }
      }
    }
    void poll()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [jobId, session])
  async function run() {
    if (!session) { onLogin(); return }
    setBusy(true); setError(""); setMessage("")
    setCompleted(false)
    try {
      const job = await request<{ jobId: string }>("/library/archive", { beginDate, endDate, diaryType, formats }, session)
      setJobId(job.jobId)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "归档未完成。")
      setBusy(false)
    }
  }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <h2 className="text-3xl font-semibold">日记归档</h2>
      <p>获取所选云端日记、更新备份并生成可阅读文档，一次完成。</p>
      <fieldset disabled={busy} className="grid gap-5 rounded-xl border p-6">
        <label className="grid gap-2">
          日记类型
          <select
            className={inputClass}
            value={diaryType}
            onChange={(e) => setType(e.target.value)}
          >
            {DIARY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-2">
            开始日期
            <input
              className={inputClass}
              type="date"
              value={beginDate}
              max={endDate}
              onChange={(e) => setBegin(e.target.value)}
            />
          </label>
          <label className="grid gap-2">
            结束日期
            <input
              className={inputClass}
              type="date"
              value={endDate}
              min={beginDate}
              max={todayString()}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
        </div>
        <section className="space-y-3">
          <h3 className="font-semibold">归档格式（可多选）</h3>
          {EXPORT_FORMATS.map((f) => <label key={f.value} className="flex items-center gap-3">
            <input type="checkbox" checked={formats.includes(f.value)} onChange={(e) => setFormats(e.target.checked ? [...formats, f.value] : formats.filter(v => v !== f.value))} />
            {f.label}{["pdf", "docx"].includes(f.value) ? "（同时保留 Markdown）" : ""}
          </label>)}
          <p className="text-sm text-muted-foreground">备份保存到 backup，可阅读文档保存到 archive。可在设置中更改归档目录。</p>
          <Button disabled={!beginDate || !endDate || !formats.length} onClick={() => void run()}>归档日记</Button>
        </section>
      </fieldset>
      <p aria-live="polite" className="break-all">
        {busy ? "正在处理… " : ""}
        {message}
      </p>
      {error && <p role="alert">{error}</p>}
      {completed && <ArchiveFolderButton />}
    </main>
  )
}

type OCRPage = {
  index: number
  name: string
  state: "success" | "failed" | "no-text"
  text: string
  error?: string
}
type OCRStatus = {
  state: string
  result?: { pages: OCRPage[] }
  error?: string
}
export function OCRPage() {
  const [files, setFiles] = useState<File[]>([])
  const [pages, setPages] = useState<OCRPage[]>([])
  const [format, setFormat] = useState<ExportFormat>("markdown")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [jobId, setJobId] = useState("")
  const fileInput = useRef<HTMLInputElement>(null)
  const pending = useRef("")
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      if (pending.current)
        void request("/ocr/cancel", { jobId: pending.current }).catch(() => {})
    }
  }, [])
  useEffect(() => {
    if (!jobId) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const job = await request<OCRStatus>("/ocr/status", { jobId })
        if (!active) return
        if (job.state === "running") timer = setTimeout(poll, 500)
        else {
          setPages(job.result?.pages || [])
          setError(job.error || "")
          setBusy(false)
          setJobId("")
          setMessage(
            job.state === "completed"
              ? "识别完成，可以逐页编辑后导出。"
              : "识别已结束。"
          )
        }
      } catch (cause) {
        if (active) {
          setError(String(cause))
          setBusy(false)
          setJobId("")
        }
      }
    }
    void poll()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [jobId])
  async function recognize() {
    setBusy(true)
    setError("")
    setPages([])
    setMessage("正在本机识别文字…")
    try {
      if (
        !files.length ||
        files.length > 20 ||
        files.reduce((sum, f) => sum + f.size, 0) > 40 * 1024 * 1024
      )
        throw new Error("请选择 1–20 张图片，总大小不超过 40 MiB。")
      const images = await Promise.all(
        files.map(
          (file) =>
            new Promise<{ name: string; data: string }>((resolve, reject) => {
              const reader = new FileReader()
              reader.onerror = () => reject(new Error("图片读取失败。"))
              reader.onload = () =>
                resolve({
                  name: file.name,
                  data: String(reader.result).split(",")[1],
                })
              reader.readAsDataURL(file)
            })
        )
      )
      if (!mounted.current) return
      const result = await request<{ jobId: string }>("/ocr/start", { images })
      pending.current = result.jobId
      if (!mounted.current) {
        await request("/ocr/cancel", { jobId: result.jobId })
        return
      }
      setJobId(result.jobId)
    } catch (cause) {
      if (mounted.current) {
        setError(cause instanceof Error ? cause.message : "识别失败。")
        setBusy(false)
      }
    }
  }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <h2 className="text-3xl font-semibold">识图转文字</h2>
      <p>本机离线识别中文、英文和混合文字，图片不会发送到 AI 服务商。</p>
      <div className="grid gap-3">
        <p>选择图片（PNG、JPG/JPEG、WEBP）</p>
        <Button type="button" className="w-fit" disabled={busy}
          onClick={() => fileInput.current?.click()}>选择文件</Button>
        <input
          ref={fileInput}
          aria-label="选择图片文件"
          className="sr-only"
          tabIndex={-1}
          type="file"
          multiple
          accept=".png,.jpg,.jpeg,.webp"
          disabled={busy}
          onChange={(e) => {
            setFiles(Array.from(e.target.files || []))
            setPages([])
            setError("")
            setMessage("")
          }}
        />
      </div>
      <ol className="list-inside list-decimal text-sm">
        {files.map((f, i) => (
          <li key={i}>{f.name}</li>
        ))}
      </ol>
      <p className="text-sm text-muted-foreground">
        按上方顺序逐张识别，最多 20 张；每张不超过 2000 万像素。不重建复杂分栏。
      </p>
      <Button disabled={busy || !files.length} onClick={() => void recognize()}>
        {busy ? "正在识别…" : "识别文字"}
      </Button>
      {busy && jobId && (
        <Button
          variant="outline"
          onClick={() =>
            void request("/ocr/cancel", { jobId }).catch((cause) =>
              setError(String(cause))
            )
          }
        >
          取消识别
        </Button>
      )}
      <p aria-live="polite" className="break-all">
        {message}
      </p>
      {error && <p role="alert">{error}</p>}
      {pages.map((page, index) => (
        <section className="grid gap-3 rounded-xl border p-5" key={page.index}>
          <h3>
            第 {index + 1} 页 · {page.name}
          </h3>
          <p>
            {page.state === "failed"
              ? page.error
              : page.state === "no-text"
                ? "未检测到文字，可手动输入。"
                : "识别成功，可编辑。"}
          </p>
          <textarea
            aria-label={`第 ${index + 1} 页文字`}
            rows={8}
            className={`${inputClass} w-full`}
            value={page.text}
            onChange={(e) =>
              setPages((previous) =>
                previous.map((p, i) =>
                  i === index ? { ...p, text: e.target.value } : p
                )
              )
            }
          />
        </section>
      ))}
      {!!pages.length && (
        <section className="grid gap-4">
          <FormatPicker value={format} onChange={setFormat} />
          <p>保存到「设置 → 归档目录」下的 archive/ocr 文件夹。</p>
          <ArchiveFolderButton area="ocr" />
          <Button
            disabled={busy || !pages.some((p) => p.text.trim())}
            onClick={async () => {
              setBusy(true)
              setError("")
              try {
                const result = await request<{ path: string }>("/ocr/export", {
                  pages: pages.map((p) => ({ text: p.text })),
                  format,
                })
                setMessage(`已导出：${result.path}`)
              } catch (cause) {
                setError(String(cause))
              } finally {
                setBusy(false)
              }
            }}
          >
            导出编辑后的文字
          </Button>
        </section>
      )}
    </main>
  )
}
