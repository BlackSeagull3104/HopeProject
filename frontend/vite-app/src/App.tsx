import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { request, type Session } from "@/lib/api"
import { pickDirectory, type ExportFormat } from "@/lib/export"
import { DiaryPreview, MediaPreview } from "@/DiaryPreview"
import { SearchPage } from "@/SearchPage"
import { AISettingsPage } from "@/AISettingsPage"
import { AIAssistantPage } from "@/AIAssistantPage"
import { ArchivePage, OCRPage, FormatPicker, inputClass } from "@/ProductPages"

const navigation = [
  ["preview", "日记预览"],
  ["archive", "日记归档"],
  ["capsules", "时间胶囊"],
  ["search", "本地搜索"],
  ["ai", "AI 日记助手"],
  ["ocr", "识图转文字"],
  ["settings", "设置"],
] as const
type Page = (typeof navigation)[number][0]
type Preferences = { exportRoot: string; exportConfigured: boolean; migrationWarning?: string }

function Login({
  onLogin,
  onClose,
}: {
  onLogin: (session: Session) => void
  onClose: () => void
}) {
  const [mode, setMode] = useState("code")
  const [mobile, setMobile] = useState("")
  const [secret, setSecret] = useState("")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [cooldown, setCooldown] = useState(0)
  useEffect(() => {
    if (!cooldown) return
    const timer = setTimeout(() => setCooldown((v) => v - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])
  return (
    <section
      role="dialog"
      aria-modal="true"
      aria-label="登录 Hope"
      className="fixed inset-0 z-40 grid place-items-center bg-background/95 p-8"
    >
      <form
        className="grid w-full max-w-md gap-5 rounded-2xl border bg-card p-8"
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          setMessage("")
          const credential = secret
          setSecret("")
          try {
            const session = await request<Session>(`/auth/login/${mode}`, {
              mobile: mobile.trim(),
              secret: credential,
            })
            setMobile("")
            onLogin(session)
          } catch (cause) {
            setMessage(cause instanceof Error ? cause.message : "登录失败。")
          } finally {
            setBusy(false)
          }
        }}
      >
        <h2 className="text-2xl font-semibold">登录 Hope</h2>
        <p>登录后可下载日记及已开启时间胶囊。</p>
        <fieldset disabled={busy} className="grid gap-4">
          <label className="grid gap-2">
            登录方式
            <select
              className={inputClass}
              value={mode}
              onChange={(e) => {
                setMode(e.target.value)
                setSecret("")
              }}
            >
              <option value="code">验证码登录</option>
              <option value="password">密码登录</option>
            </select>
          </label>
          <label className="grid gap-2">
            手机号
            <input
              required
              type="tel"
              autoComplete="username"
              className={inputClass}
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
            />
          </label>
          <label className="grid gap-2">
            {mode === "code" ? "验证码" : "密码"}
            <input
              required
              type="password"
              autoComplete={
                mode === "code" ? "one-time-code" : "current-password"
              }
              className={inputClass}
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
            />
          </label>
          {mode === "code" && (
            <Button
              type="button"
              variant="outline"
              disabled={!mobile.trim() || cooldown > 0}
              onClick={async () => {
                setBusy(true)
                setCooldown(60)
                try {
                  await request("/auth/send-code", { mobile: mobile.trim() })
                  setMessage("验证码已发送。")
                } catch (cause) {
                  setMessage(String(cause))
                } finally {
                  setBusy(false)
                }
              }}
            >
              {cooldown ? `${cooldown} 秒后重发` : "发送验证码"}
            </Button>
          )}
          <Button type="submit">{busy ? "正在登录…" : "登录"}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            继续离线浏览
          </Button>
        </fieldset>
        <p role="status">{message}</p>
      </form>
    </section>
  )
}

type Capsule = {
  id: string
  title?: string
  content?: string
  created_at?: string
  media: { key: string; kind: string }[]
}
function OpenedCapsules({
  session,
  onLogin,
}: {
  session: Session | null
  onLogin: () => void
}) {
  const [items, setItems] = useState<Capsule[]>([])
  const [format, setFormat] = useState<ExportFormat>("markdown")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  useEffect(() => {
    let active = true
    request<{ items: Capsule[] }>("/library/capsules", {}, session ?? undefined)
      .then((r) => {
        if (active) setItems(r.items)
      })
      .catch((c) => {
        if (active) setMessage(String(c))
      })
    return () => {
      active = false
    }
  }, [session])
  async function update() {
    if (!session) {
      onLogin()
      return
    }
    setBusy(true)
    setMessage("正在归档已开启的时间胶囊…")
    try {
      const started = await request<{ jobId: string }>(
        "/library/capsules/update",
        {},
        session
      )
      while (true) {
        const state = await request<{
          state: string
          stage: string
          mediaWarning?: string
        }>(`/jobs/${started.jobId}`, undefined, session)
        setMessage(state.stage)
        if (state.state !== "running") {
          if (state.state === "failed") throw new Error(state.stage)
          if (state.mediaWarning) setMessage(state.mediaWarning)
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 700))
      }
      const r = await request<{ items: Capsule[] }>(
        "/library/capsules",
        {},
        session
      )
      setItems(r.items)
    } catch (c) {
      setMessage(String(c))
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <h2 className="text-3xl font-semibold">时间胶囊</h2>
      <p>仅归档已经开启、当前可读取的时间胶囊。</p>
      <Button disabled={busy} onClick={() => void update()}>
        下载 / 更新已开启胶囊
      </Button>
      <div aria-live="polite" className="break-all">
        {message}
      </div>
      {!items.length && <p>还没有本地已开启时间胶囊。</p>}
      {items.map((item) => (
        <article key={item.id} className="rounded-xl border p-6">
          <h3 className="font-semibold">
            {item.title || "时间胶囊"} · {item.created_at}
          </h3>
          <p className="mt-3 whitespace-pre-wrap">
            {item.content || "此胶囊没有文字内容。"}
          </p>
          {item.media.map((media) => (
            <MediaPreview
              key={media.key}
              media={media}
              kind={media.kind}
              session={session ?? undefined}
            />
          ))}
        </article>
      ))}
      {!!items.length && (
        <section className="grid gap-3">
          <FormatPicker value={format} onChange={setFormat} />
          <p>保存到归档目录下的 capsules 文件夹。</p>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              try {
                const r = await request<{ path: string }>(
                  "/library/capsules/export",
                  { format },
                  session ?? undefined
                )
                setMessage(`已导出：${r.path}`)
              } catch (c) {
                setMessage(String(c))
              } finally {
                setBusy(false)
              }
            }}
          >
            导出已开启胶囊
          </Button>
        </section>
      )}
    </main>
  )
}

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [page, setPage] = useState<Page>("preview")
  const [login, setLogin] = useState(false)
  const [preferences, setPreferences] = useState<Preferences>({
    exportRoot: "",
    exportConfigured: false,
  })
  const [onboarding, setOnboarding] = useState(false)
  const [error, setError] = useState("")
  useEffect(() => {
    let active = true
    request<Preferences>("/settings/read", {})
      .then((r) => {
        if (active) {
          setPreferences(r)
          setOnboarding(!r.exportConfigured)
        }
      })
      .catch((c) => {
        if (active) setError(String(c))
      })
    return () => {
      active = false
    }
  }, [])
  async function chooseDirectory() {
    try {
      const selected = await pickDirectory(preferences.exportRoot)
      if (selected === null) {
        setOnboarding(false)
        return
      }
      const next = await request<Preferences>("/settings/save", {
        exportRoot: selected,
      })
      setPreferences(next)
      setOnboarding(false)
      setError("")
    } catch (c) {
      setError(c instanceof Error ? c.message : "无法保存归档目录。")
    }
  }
  return (
    <div className="min-h-svh md:grid md:grid-cols-[220px_minmax(0,1fr)]">
      <aside className="flex flex-col border-r bg-sidebar p-6">
        <h1 className="mb-2 text-lg font-semibold">Hope Archive</h1>
        <p className="mb-10 text-xs text-muted-foreground">你的本地日记档案</p>
        <nav className="flex flex-wrap gap-2 md:flex-col">
          {navigation.map(([id, label]) => (
            <Button
              key={id}
              variant={page === id ? "secondary" : "ghost"}
              className="justify-start"
              aria-current={page === id ? "page" : undefined}
              onClick={() => setPage(id)}
            >
              {label}
            </Button>
          ))}
        </nav>
        {session && (
          <p className="mt-auto pt-10 text-xs leading-6 text-muted-foreground">
            已登录：{session.displayName?.trim() || "Hope 用户"}
          </p>
        )}
      </aside>
      <div>
        <header className="flex items-center justify-between border-b px-8 py-5">
          <span>{navigation.find(([id]) => id === page)?.[1]}</span>
          <Button
            variant="ghost"
            onClick={async () => {
              if (!session) {
                setLogin(true)
                return
              }
              try {
                await request("/auth/logout", {}, session)
                setSession(null)
              } catch (c) {
                setError(String(c))
              }
            }}
          >
            {session ? "退出登录" : "登录 Hope"}
          </Button>
        </header>
        {error && (
          <p role="alert" className="p-5 text-destructive">
            {error}
          </p>
        )}
        {page === "preview" && (
          <DiaryPreview
            key={session?.token || "offline"}
            session={session ?? undefined}
            onArchive={() => setPage("archive")}
            onLogin={() => setLogin(true)}
          />
        )}
        {page === "archive" && (
          <ArchivePage
            key={session?.token || "offline"}
            session={session}
            onLogin={() => setLogin(true)}
          />
        )}
        {page === "capsules" && (
          <OpenedCapsules
            key={session?.token || "offline"}
            session={session}
            onLogin={() => setLogin(true)}
          />
        )}
        {page === "search" && (
          <SearchPage
            key={session?.token || "offline"}
            session={session ?? undefined}
            onArchive={() => setPage("archive")}
          />
        )}
        {page === "ai" && (
          <AIAssistantPage
            key={session?.token || "offline"}
            session={session ?? undefined}
            onSettings={() => setPage("settings")}
            onArchive={() => setPage("archive")}
          />
        )}
        {page === "ocr" && <OCRPage />}
        {page === "settings" && (
          <div>
            <section className="mx-auto max-w-3xl space-y-5 p-8">
              <h2 className="text-3xl font-semibold">归档目录</h2>
              <p className="break-all">
                {preferences.exportRoot || "尚未设置归档目录。"}
              </p>
              <Button onClick={() => void chooseDirectory()}>
                选择 / 更改归档目录
              </Button>
              <p>
                Hope Archive 会自动管理 backup 中的备份数据与 archive 中的可阅读文档。
              </p>
              {preferences.migrationWarning && <p role="alert">{preferences.migrationWarning}</p>}
            </section>
            <AISettingsPage />
          </div>
        )}
      </div>
      {login && (
        <Login
          onClose={() => setLogin(false)}
          onLogin={(value) => {
            setSession(value)
            setLogin(false)
          }}
        />
      )}
      {onboarding && (
        <section
          role="dialog"
          aria-modal="true"
          aria-label="选择归档目录"
          className="fixed inset-0 z-50 grid place-items-center bg-background/95 p-8"
        >
          <div className="max-w-lg space-y-5 rounded-2xl border bg-card p-8">
            <h2 className="text-2xl font-semibold">选择归档目录</h2>
            <p>
              Hope Archive
              会自动管理备份数据与可阅读文档。之后可以在「设置」中修改。
            </p>
            <Button onClick={() => void chooseDirectory()}>选择文件夹</Button>
            <Button variant="ghost" onClick={() => setOnboarding(false)}>
              稍后设置
            </Button>
            {error && <p role="alert">{error}</p>}
          </div>
        </section>
      )}
    </div>
  )
}
export default App
