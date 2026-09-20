import { useState } from "react"
import { request, type Session } from "@/lib/api"
import { DIARY_TYPES } from "@/lib/diary"
import { Button } from "@/components/ui/button"
import { highlightedParts } from "@/lib/search"

type Item = {
  id: string
  date: string
  diaryType: string
  contentType: string
  title: string
  snippet: string
}
type Results = { items: Item[]; total: number; nextOffset: number }
type Detail = Omit<Item, "snippet"> & { body: string }
const input = "h-10 rounded-lg border bg-background px-3 text-sm min-w-0"
function label(item: Item | Detail) {
  return item.contentType === "capsule"
    ? "时间胶囊 · 创建日期"
    : DIARY_TYPES.find((t) => t.value === item.diaryType)?.label ||
        "未知日记类型"
}
export function SearchPage({
  session,
  onArchive,
}: {
  session?: Session
  onArchive: () => void
}) {
  const [query, setQuery] = useState("")
  const [beginDate, setBegin] = useState("")
  const [endDate, setEnd] = useState("")
  const [diaryType, setDiaryType] = useState("all")
  const [contentType, setContentType] = useState("all")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [results, setResults] = useState<Results | null>(null)
  const [applied, setApplied] = useState({
    query: "",
    beginDate: "",
    endDate: "",
    diaryType: "all",
    contentType: "all",
  })
  const [detail, setDetail] = useState<Detail | null>(null)
  async function search(more = false) {
    setBusy(true)
    setError("")
    setMessage("")
    setDetail(null)
    const filters = more
      ? applied
      : { query, beginDate, endDate, diaryType, contentType }
    if (!more) setResults(null)
    try {
      const data = await request<Results>(
        "/library/search/query",
        {
          ...filters,
          offset: more ? results?.nextOffset : 0,
        },
        session
      )
      setApplied(filters)
      setResults(
        more && results
          ? { ...data, items: [...results.items, ...data.items] }
          : data
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "搜索失败。")
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <h1 className="text-3xl font-semibold">本地搜索</h1>
      <p className="text-sm text-muted-foreground">
        搜索已下载到本地的日记，无需联网。尚未归档的日记不会出现在搜索结果中。时间胶囊仅检索已开启内容。
      </p>
      <Button variant="ghost" onClick={onArchive}>
        前往日记归档
      </Button>
      <fieldset disabled={busy} className="space-y-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            void search()
          }}
        >
          <input
            aria-label="关键词"
            className={`${input} flex-1`}
            placeholder="输入关键词，如：乒乓球"
            maxLength={200}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" disabled={!query.trim()}>搜索</Button>
        </form>
        <div className="flex flex-wrap gap-3">
          <label className="grid gap-1 text-sm">
            开始日期
            <input
              type="date"
              className={input}
              value={beginDate}
              max={endDate || undefined}
              onChange={(e) => setBegin(e.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm">
            结束日期
            <input
              type="date"
              className={input}
              value={endDate}
              min={beginDate || undefined}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm">
            日记类型
            <select
              className={input}
              value={diaryType}
              onChange={(e) => setDiaryType(e.target.value)}
            >
              {DIARY_TYPES.map((t) => (
                <option value={t.value} key={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            内容类型
            <select
              className={input}
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
            >
              <option value="all">全部内容</option>
              <option value="diary">日记</option>
              <option value="capsule">时间胶囊</option>
            </select>
          </label>
        </div>
        <Button
          variant="outline"
          onClick={async () => {
            setBusy(true)
            setError("")
            setResults(null)
            setDetail(null)
            try {
              const result = await request<{ entries: number }>(
                "/library/search/rebuild",
                {},
                session
              )
              setMessage(`索引已重建，共 ${result.entries} 条。`)
            } catch (cause) {
              setError(cause instanceof Error ? cause.message : "重建失败。")
            } finally {
              setBusy(false)
            }
          }}
        >
          重建索引
        </Button>
      </fieldset>
      <div aria-live="polite">
        {busy ? (
          <p>正在读取本地归档…</p>
        ) : error ? (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        ) : message ? (
          <p>{message}</p>
        ) : results ? (
          <p>
            {results.total
              ? `找到 ${results.total} 条结果 · ${applied.query}`
              : "没有找到匹配的内容，换个关键词试试吧。"}
          </p>
        ) : (
          <p className="text-muted-foreground">
            输入关键词开始搜索，日期留空表示不限日期。
          </p>
        )}
      </div>
      {!error &&
        results?.items.map((item) => (
          <button
            key={item.id}
            disabled={busy}
            className="block w-full rounded-xl border p-5 text-left hover:bg-muted/50"
            onClick={async () => {
              setBusy(true)
              setError("")
              try {
                setDetail(
                  await request<Detail>(
                    "/library/search/detail",
                    {
                      id: item.id,
                    },
                    session
                  )
                )
              } catch (cause) {
                setError(cause instanceof Error ? cause.message : "读取失败。")
              } finally {
                setBusy(false)
              }
            }}
          >
            <p className="font-medium">
              {item.date || "日期未知"} · {label(item)}
            </p>
            {item.title && <p>{item.title}</p>}
            <p className="mt-2 break-words whitespace-pre-wrap">
              {highlightedParts(item.snippet, applied.query).map((part, i) =>
                part.match ? <mark key={i}>{part.text}</mark> : part.text
              )}
            </p>

          </button>
        ))}
      {results && results.nextOffset < results.total && (
        <Button
          disabled={busy}
          variant="outline"
          onClick={() => void search(true)}
        >
          加载更多
        </Button>
      )}
      {detail && (
        <section className="rounded-xl border bg-card p-6">
          <h2 className="text-xl font-semibold">
            本地详情 · {detail.date} · {label(detail)}
          </h2>
          <p className="mt-4 break-words whitespace-pre-wrap">{detail.body}</p>

        </section>
      )}
    </main>
  )
}
