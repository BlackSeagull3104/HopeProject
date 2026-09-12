import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { ApiError, request, type Session } from "@/lib/api"
import { pickDirectory } from "@/lib/export"

type Media = { key: string; kind: "image" | "video" | "audio" }
type Capsule = {
  id: string
  title: string | null
  keywords: string | null
  content: string | null
  status: string
  created_at: string | null
  scheduled_at: string | null
  opened_at: string | null
  updated_at: string | null
  content_available: boolean
  media: Media[]
}
type Page = {
  items: Capsule[]
  nextOffset: number
  hasMore: boolean
  total: number
  outputDir: string
}
const inputClass =
  "h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm"
const statusName = (value: string) =>
  ({ opened: "已开启", unopened: "未开启" })[value] || "状态未知"

function MediaPreview({
  item,
  id,
  session,
}: {
  item: Media
  id: string
  session: Session
}) {
  const [source, setSource] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const guard = useRef(false)
  async function load() {
    if (guard.current) return
    guard.current = true
    setBusy(true)
    setError("")
    try {
      const data = await request<{ mime: string; data: string }>(
        "/capsules/media",
        { id, key: item.key },
        session
      )
      setSource(`data:${data.mime};base64,${data.data}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "媒体加载失败。")
    } finally {
      guard.current = false
      setBusy(false)
    }
  }
  return (
    <div className="space-y-2">
      {!source && (
        <Button variant="outline" disabled={busy} onClick={() => void load()}>
          {busy
            ? "正在保存媒体…"
            : `保存并预览${item.kind === "image" ? "图片" : item.kind === "video" ? "视频" : "音频"}`}
        </Button>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {source &&
        (item.kind === "image" ? (
          <img
            src={source}
            alt="时间胶囊图片"
            className="max-h-[600px] max-w-full object-contain"
          />
        ) : item.kind === "video" ? (
          <video src={source} controls className="max-h-[600px] max-w-full" />
        ) : (
          <audio src={source} controls />
        ))}
    </div>
  )
}

export function CapsulePage({
  session,
  defaultOutputDir,
  onExpired,
}: {
  session: Session
  defaultOutputDir: string
  onExpired: () => void
}) {
  const [status, setStatus] = useState("opened")
  const [directory, setDirectory] = useState(defaultOutputDir)
  const [page, setPage] = useState<Page | null>(null)
  const [selected, setSelected] = useState<Capsule | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const guard = useRef(false)
  async function action(work: () => Promise<void>) {
    if (guard.current) return
    guard.current = true
    setBusy(true)
    setError("")
    try {
      await work()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "时间胶囊加载失败。")
      if (cause instanceof ApiError && cause.status === 401) onExpired()
    } finally {
      guard.current = false
      setBusy(false)
    }
  }
  function load(nextStatus = status, more = false) {
    void action(async () => {
      setSelected(null)
      if (!more) setPage(null)
      const data = await request<Page>(
        "/capsules/list",
        {
          status: nextStatus,
          outputDir: directory,
          offset: more ? (page?.nextOffset ?? 0) : 0,
        },
        session
      )
      setPage({
        ...data,
        items: more ? [...(page?.items ?? []), ...data.items] : data.items,
      })
    })
  }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8 lg:p-12">
      <h2 className="text-3xl font-semibold">时间胶囊</h2>
      <p className="text-sm text-muted-foreground">
        独立时间胶囊，区别于日记中的“胶囊日记”。加载的数据保存在本机；未开启内容不提供预览或开锁。
      </p>
      <fieldset disabled={busy} className="space-y-4 rounded-xl border p-6">
        <label className="grid gap-2 text-sm">
          归档根目录（当前会话固定）
          <div className="flex gap-2">
            <input
              className={inputClass}
              value={directory}
              disabled={page !== null}
              onChange={(e) => setDirectory(e.target.value)}
            />
            <Button
              variant="outline"
              disabled={page !== null}
              onClick={() =>
                void action(async () => {
                  const result = await pickDirectory(directory)
                  if (result) setDirectory(result)
                })
              }
            >
              ...
            </Button>
          </div>
        </label>
        <label className="grid gap-2 text-sm">
          状态
          <select
            className={inputClass}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              load(e.target.value)
            }}
          >
            <option value="opened">已开启</option>
            <option value="unopened">未开启</option>
          </select>
        </label>
        <Button onClick={() => load()}>加载 / 刷新列表</Button>
      </fieldset>
      {busy && <p role="status">正在加载…</p>}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {page && (
        <>
          <p className="text-sm break-all">
            已加载 {page.items.length} / {page.total} 个 · 保存位置：
            {page.outputDir}
          </p>
          {page.items.length === 0 && <p>此状态下没有时间胶囊。</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {page.items.map((item) => (
              <Button
                key={item.id}
                variant="outline"
                disabled={busy}
                className="h-auto justify-start p-4 text-left whitespace-normal"
                onClick={() =>
                  void action(async () =>
                    setSelected(
                      await request<Capsule>(
                        "/capsules/detail",
                        { id: item.id },
                        session
                      )
                    )
                  )
                }
              >
                <span>
                  {item.title || item.keywords || "时间胶囊"}
                  <br />
                  <span className="text-xs text-muted-foreground">
                    {statusName(item.status)} ·{" "}
                    {item.created_at || "创建日期未知"}
                  </span>
                </span>
              </Button>
            ))}
          </div>
          {page.hasMore && (
            <Button
              disabled={busy}
              variant="outline"
              onClick={() => load(status, true)}
            >
              加载更多
            </Button>
          )}
        </>
      )}
      {selected && (
        <section className="space-y-4 rounded-xl border p-6">
          <h3 className="text-xl font-semibold">
            {selected.title || selected.keywords || "时间胶囊"}
          </h3>
          <p>{statusName(selected.status)}</p>
          <dl className="grid gap-2 text-sm">
            <div>创建：{selected.created_at || "未知"}</div>
            <div>计划开启：{selected.scheduled_at || "未知"}</div>
            <div>用户开启日期：{selected.opened_at || "未提供"}</div>
            <div>更新：{selected.updated_at || "未提供"}</div>
          </dl>
          <p className="break-words whitespace-pre-wrap">
            {selected.content_available
              ? selected.content || "未提供正文。"
              : "内容尚未开放、状态未知或已清空，仅展示元信息。"}
          </p>
          {selected.media.map((item) => (
            <MediaPreview
              key={`${selected.id}:${item.key}`}
              item={item}
              id={selected.id}
              session={session}
            />
          ))}
        </section>
      )}
    </main>
  )
}
