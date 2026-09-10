import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react"
import { Archive, FileText, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ApiError, request, type Job, type Session } from "@/lib/api"
import {
  EXPORT_FORMATS,
  dateRangeError,
  pickDirectory,
  todayString,
  type ExportFormat,
} from "@/lib/export"

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid min-w-0 gap-2 text-sm font-medium">
      {label}
      {children}
    </label>
  )
}
const inputClass =
  "h-10 min-w-0 w-full rounded-lg border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [mode, setMode] = useState<"code" | "password">("code")
  const [mobile, setMobile] = useState("")
  const [secret, setSecret] = useState("")
  const [page, setPage] = useState<"archive" | "export">("archive")
  const [beginDate, setBeginDate] = useState(
    () => todayString().slice(0, 8) + "01"
  )
  const [endDate, setEndDate] = useState(todayString)
  const [outputDir, setOutputDir] = useState("")
  const [inputPath, setInputPath] = useState("")
  const [archiveDir, setArchiveDir] = useState("")
  const [exportDir, setExportDir] = useState("")
  const [exportFormat, setExportFormat] = useState<ExportFormat>("markdown")
  const [health, setHealth] = useState("正在连接本地服务…")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const guard = useRef(false)
  const [cooldown, setCooldown] = useState(0)
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const running = busy || job?.state === "running"

  useEffect(() => {
    let alive = true
    request<{ defaultOutputDir: string }>("/health")
      .then((data) => {
        if (alive) {
          setHealth("本地服务已连接")
          setOutputDir((current) => current || data.defaultOutputDir)
        }
      })
      .catch(() => {
        if (alive) setHealth("本地服务未连接，请启动 Python API 后刷新。")
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (!cooldown) return
    const timer = window.setTimeout(
      () => setCooldown((value) => Math.max(0, value - 1)),
      1000
    )
    return () => window.clearTimeout(timer)
  }, [cooldown])

  useEffect(() => {
    if (!jobId || !session) return
    let alive = true
    let timer: number
    async function poll() {
      try {
        const next = await request<Job>(`/jobs/${jobId}`, undefined, session!)
        if (!alive) return
        setJob(next)
        setError("")
        if (next.state === "running") timer = window.setTimeout(poll, 1000)
        else {
          setJobId(null)
          if (next.result && next.result.media) {
            setInputPath(
              next.result.outputDir + "/processed/diaries.normalized.json"
            )
            setArchiveDir(next.result.outputDir + "/archive")
          }
        }
      } catch (cause) {
        if (!alive) return
        setError(cause instanceof Error ? cause.message : "读取任务状态失败。")
        if (
          cause instanceof ApiError &&
          (cause.status === 401 || cause.status === 404)
        ) {
          setJobId(null)
          setJob(null)
          if (cause.status === 401) setSession(null)
        } else timer = window.setTimeout(poll, 3000)
      }
    }
    void poll()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [jobId, session])

  async function action(work: () => Promise<void>) {
    if (guard.current || job?.state === "running") return
    guard.current = true
    setBusy(true)
    setError("")
    setMessage("")
    try {
      await work()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败。")
      if (cause instanceof ApiError && cause.status === 401) setSession(null)
    } finally {
      guard.current = false
      setBusy(false)
    }
  }

  function login(event: FormEvent) {
    event.preventDefault()
    void action(async () => {
      const credential = secret
      setSecret("")
      const current = await request<Session>(`/auth/login/${mode}`, {
        mobile: mobile.trim(),
        secret: credential,
      })
      setSession(current)
      setMobile("")
      setPage("archive")
      setJob(null)
    })
  }

  function start(event: FormEvent) {
    event.preventDefault()
    void action(async () => {
      const validation = dateRangeError(beginDate, endDate)
      if (validation) throw new Error(validation)
      const body =
        page === "archive"
          ? { beginDate, endDate, outputDir }
          : {
              inputPath,
              archiveDir,
              outputDir: exportDir,
              format: exportFormat,
              beginDate,
              endDate,
            }
      const data = await request<{ jobId: string }>(
        page === "archive" ? "/archive/download" : "/export/document",
        body,
        session!
      )
      setJob({ state: "running", stage: "正在准备…" })
      setJobId(data.jobId)
    })
  }

  const notices = (
    <div aria-live="polite" className="space-y-3">
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
        >
          {error}
        </p>
      )}
      {message && (
        <p className="rounded-lg border bg-muted/50 p-4 text-sm">{message}</p>
      )}
    </div>
  )

  if (!session)
    return (
      <main className="grid min-h-svh place-items-center bg-muted/25 p-8">
        <section className="w-full max-w-5xl overflow-hidden rounded-2xl border bg-card shadow-sm md:grid md:grid-cols-2">
          <div className="flex flex-col justify-between border-b bg-muted/35 p-12 md:border-r md:border-b-0">
            <div>
              <p className="text-sm tracking-widest text-muted-foreground">
                HOPE ARCHIVE
              </p>
              <h1 className="mt-10 text-3xl leading-relaxed font-semibold">
                把日记，
                <br />
                好好留在身边。
              </h1>
              <p className="mt-5 max-w-xs text-sm leading-7 text-muted-foreground">
                下载自己的 Hope 日记，保存图片与媒体，整理为可阅读的本地
                Markdown 归档。
              </p>
            </div>
            <p className="mt-12 text-xs text-muted-foreground">
              本地归档 · 原文保留
            </p>
          </div>
          <div className="space-y-6 p-10 lg:p-12">
            <div>
              <h2 className="text-2xl font-semibold">登录 Hope</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                登录信息仅保留在本次页面运行期间。
              </p>
            </div>
            <div
              className="flex gap-2 rounded-lg bg-muted p-1"
              aria-label="登录方式"
            >
              {(["code", "password"] as const).map((value) => (
                <Button
                  key={value}
                  type="button"
                  className="flex-1"
                  variant={mode === value ? "outline" : "ghost"}
                  aria-pressed={mode === value}
                  disabled={busy}
                  onClick={() => {
                    setMode(value)
                    setSecret("")
                    setError("")
                  }}
                >
                  {value === "code" ? "验证码登录" : "密码登录"}
                </Button>
              ))}
            </div>
            <form onSubmit={login} className="space-y-5">
              <fieldset disabled={busy} className="space-y-5">
                <Field label="手机号">
                  <input
                    className={inputClass}
                    type="tel"
                    autoComplete="username"
                    required
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value)}
                  />
                </Field>
                <Field label={mode === "code" ? "验证码" : "密码"}>
                  <input
                    className={inputClass}
                    type="password"
                    autoComplete={
                      mode === "code" ? "one-time-code" : "current-password"
                    }
                    required
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                  />
                </Field>
                {mode === "code" && (
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!mobile.trim() || cooldown > 0}
                    onClick={() =>
                      void action(async () => {
                        setCooldown(60)
                        await request("/auth/send-code", {
                          mobile: mobile.trim(),
                        })
                        setMessage("验证码发送成功，请查看手机。")
                      })
                    }
                  >
                    {cooldown ? `${cooldown} 秒后重发` : "发送验证码"}
                  </Button>
                )}
                <Button type="submit" className="w-full" size="lg">
                  {busy ? "请求进行中…" : "登录"}
                </Button>
              </fieldset>
            </form>
            {notices}
            <p className="text-xs text-muted-foreground">{health}</p>
          </div>
        </section>
      </main>
    )

  return (
    <div className="min-h-svh md:grid md:grid-cols-[220px_minmax(0,1fr)]">
      <aside className="flex flex-col border-r bg-sidebar p-6">
        <h1 className="mb-2 text-lg font-semibold">Hope Archive</h1>
        <p className="mb-10 text-xs text-muted-foreground">你的本地日记档案</p>
        <nav className="flex gap-2 md:flex-col">
          {(["archive", "export"] as const).map((value) => (
            <Button
              key={value}
              variant={page === value ? "secondary" : "ghost"}
              className="justify-start"
              aria-current={page === value ? "page" : undefined}
              onClick={() => setPage(value)}
            >
              {value === "archive" ? <Archive /> : <FileText />}
              {value === "archive" ? "下载归档" : "导出"}
            </Button>
          ))}
        </nav>
        <p className="mt-auto pt-10 text-xs leading-6 text-muted-foreground">
          已登录：{session.displayName?.trim() || "Hope 用户"}
          <br />
          登录身份自动用于归档
        </p>
      </aside>
      <div>
        <header className="flex items-center justify-between border-b px-10 py-5">
          <span className="text-sm text-muted-foreground">
            个人档案 / {page === "archive" ? "下载归档" : "导出"}
          </span>
          <Button
            variant="ghost"
            disabled={running}
            onClick={() =>
              void action(async () => {
                await request("/auth/logout", {}, session)
                setSession(null)
                setJob(null)
                setInputPath("")
                setArchiveDir("")
                setExportDir("")
              })
            }
          >
            <LogOut />
            退出登录
          </Button>
        </header>
        <main className="mx-auto max-w-5xl space-y-7 p-8 lg:p-12">
          <div>
            <h2 className="text-3xl font-semibold">
              {page === "archive" ? "下载归档" : "导出"}
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              {page === "archive"
                ? "选择日期范围，将日记、媒体和 Markdown 保存到电脑。"
                : "使用已下载的标准化日记，按日期导出所选格式，无需重新下载。"}
            </p>
          </div>
          <section className="rounded-xl border bg-card p-7 shadow-xs">
            <form onSubmit={start}>
              <fieldset disabled={running} className="min-w-0 space-y-6">
                <div className="grid gap-6 sm:grid-cols-2">
                  <Field label="开始日期">
                    <input
                      className={inputClass}
                      type="date"
                      required
                      max={endDate < todayString() ? endDate : todayString()}
                      value={beginDate}
                      onChange={(e) => setBeginDate(e.target.value)}
                    />
                  </Field>
                  <Field label="结束日期">
                    <input
                      className={inputClass}
                      type="date"
                      required
                      min={beginDate}
                      max={todayString()}
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                    />
                  </Field>
                </div>
                {page === "archive" ? (
                  <>
                    <Field label="归档根目录">
                      <div className="flex items-center gap-2">
                        <input
                          className={inputClass}
                          required
                          value={outputDir}
                          onChange={(e) => setOutputDir(e.target.value)}
                          placeholder="输入本机文件夹的完整路径"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          aria-label="选择输出文件夹"
                          onClick={() =>
                            void action(async () => {
                              const selected = await pickDirectory(outputDir)
                              if (selected !== null) setOutputDir(selected)
                            })
                          }
                        >
                          ...
                        </Button>
                      </div>
                    </Field>
                    <p className="text-sm leading-6 text-muted-foreground">
                      每次创建独立的 hope-archive-* 文件夹。自动下载媒体并生成
                      Markdown。
                      <br />
                      默认日记类型；后端自动分页，每页 20 条。
                    </p>
                  </>
                ) : (
                  <>
                    <Field label="标准化日记 JSON 文件">
                      <input
                        className={inputClass}
                        required
                        value={inputPath}
                        onChange={(e) => setInputPath(e.target.value)}
                        placeholder="…/processed/diaries.normalized.json"
                      />
                    </Field>
                    <Field label="媒体归档目录">
                      <input
                        className={inputClass}
                        required
                        value={archiveDir}
                        onChange={(e) => setArchiveDir(e.target.value)}
                        placeholder="包含 media_manifest.json 的 archive 文件夹"
                      />
                    </Field>
                    <Field label="导出格式">
                      <select
                        className={inputClass}
                        value={exportFormat}
                        onChange={(e) =>
                          setExportFormat(e.target.value as ExportFormat)
                        }
                      >
                        {EXPORT_FORMATS.map((format) => (
                          <option key={format.value} value={format.value}>
                            {format.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="输出目录（可选）">
                      <div className="flex items-center gap-2">
                        <input
                          className={inputClass}
                          value={exportDir}
                          onChange={(e) => setExportDir(e.target.value)}
                          placeholder="留空则保存到媒体归档目录"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          aria-label="选择输出文件夹"
                          onClick={() =>
                            void action(async () => {
                              const selected = await pickDirectory(exportDir)
                              if (selected !== null) setExportDir(selected)
                            })
                          }
                        >
                          ...
                        </Button>
                      </div>
                    </Field>
                    <p className="text-sm leading-6 text-muted-foreground">
                      相同文件自动跳过，不覆盖内容不同的文件。媒体保留原位置。
                      <br />
                      请仅选择本人归档；旧数据缺少作者信息时无法自动核对归属。
                    </p>
                  </>
                )}
                <Button type="submit" size="lg">
                  {running
                    ? "任务进行中…"
                    : page === "archive"
                      ? "下载归档"
                      : "生成导出文件"}
                </Button>
              </fieldset>
            </form>
          </section>
          {notices}
          {job && (
            <section
              aria-live="polite"
              className="space-y-4 rounded-xl border bg-card p-7"
            >
              <h3 className="font-medium">任务状态：{job.stage}</h3>
              {job.state === "running" && (
                <p className="text-sm text-muted-foreground">
                  正在处理，请保留页面和 Python 服务；完成前请勿刷新。
                </p>
              )}
              {job.result && (
                <>
                  <div className="grid gap-4 text-sm sm:grid-cols-3">
                    <p>日记：{job.result.diaryCount} 篇</p>
                    <p>
                      {job.result.format || "markdown"}：
                      {(job.result.export || job.result.markdown)?.generated}{" "}
                      新建 /{" "}
                      {(job.result.export || job.result.markdown)?.skipped} 跳过
                      / {(job.result.export || job.result.markdown)?.failed}{" "}
                      失败
                    </p>
                    {job.result.media && (
                      <p>
                        媒体：{job.result.media.downloaded} 保存 /{" "}
                        {job.result.media.skipped} 跳过 /{" "}
                        {job.result.media.failed} 失败
                      </p>
                    )}
                  </div>
                  <p className="rounded-lg bg-muted/50 p-3 text-sm break-all">
                    {job.result.outputDir}
                  </p>
                </>
              )}
              {job.outputDir && (
                <p className="text-sm break-all">已保存文件：{job.outputDir}</p>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
