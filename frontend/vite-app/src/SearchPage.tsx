import { useState } from "react"
import { request } from "@/lib/api"
import { pickDirectory } from "@/lib/export"
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
  source: string
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
export function SearchPage({ defaultRoot }: { defaultRoot: string }) {
  const [root, setRoot] = useState(defaultRoot)
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
    root: "",
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
      : { root, query, beginDate, endDate, diaryType, contentType }
    if (!more) setResults(null)
    try {
      const data = await request<Results>("/search/query", {
        ...filters,
        offset: more ? results?.nextOffset : 0,
      })
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
        搜索已保存的归档，无需联网或登录
        Hope。时间胶囊按创建日期筛选，仅检索已开启内容。
      </p>
      <fieldset disabled={busy} className="space-y-4">
        <label className="grid gap-2 text-sm">
          归档根目录
          <div className="flex gap-2">
            <input
              className={`${input} flex-1`}
              value={root}
              onChange={(e) => setRoot(e.target.value)}
            />
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const p = await pickDirectory(root)
                  if (p) setRoot(p)
                } catch (cause) {
                  setError(
                    cause instanceof Error ? cause.message : "目录选择失败。"
                  )
                }
              }}
            >
              ...
            </Button>
          </div>
        </label>
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
          <Button disabled={!query.trim() || !root}>搜索</Button>
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
          disabled={!root}
          onClick={async () => {
            setBusy(true)
            setError("")
            setResults(null)
            setDetail(null)
            try {
              const result = await request<{ entries: number }>(
                "/search/rebuild",
                { root }
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
            选择归档目录，输入关键词开始搜索。
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
                  await request<Detail>("/search/detail", {
                    root: applied.root,
                    id: item.id,
                  })
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
            <p className="mt-2 text-xs break-all text-muted-foreground">
              {item.source}
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
          <p className="mt-4 text-xs break-all text-muted-foreground">
            来源：{detail.source}
          </p>
        </section>
      )}
    </main>
  )
}
