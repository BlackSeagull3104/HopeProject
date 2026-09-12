import { useEffect, useState } from "react"
import { request, type Session, ApiError } from "@/lib/api"
import { DIARY_TYPES, type DiaryType } from "@/lib/diary"
import { todayString } from "@/lib/export"
import { Button } from "@/components/ui/button"

type Media = { key?: string; media_name?: string }
type Diary = {
  id: string | number
  note_date: string
  diary_type: string
  original_text?: string
  original_text_secondary?: string
  emotion_label?: string
  weather_label?: string
  content: { kind: string; text?: string; media: Media[] }[]
  comments: {
    items: {
      text?: string
      from_name?: string
      to_name?: string
      author?: { name?: string }
      created_at?: string
    }[]
  }[]
}
type Result = { diaries: Diary[] }
type State = { key: string; loading: boolean; error?: string; data?: Result }

function MediaPreview({
  media,
  kind,
  session,
}: {
  media: Media
  kind: string
  session: Session
}) {
  const [source, setSource] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  return (
    <div className="my-3 space-y-2">
      <p className="text-sm text-muted-foreground">
        {kind === "image"
          ? "图片"
          : kind === "video"
            ? "视频"
            : kind === "audio"
              ? "音频"
              : "媒体"}
        {media.media_name ? ` · ${media.media_name}` : ""}
      </p>
      {!source && (
        <Button
          variant="outline"
          disabled={busy || !media.key}
          onClick={async () => {
            setBusy(true)
            setError("")
            try {
              setSource(
                (
                  await request<{ source: string }>(
                    "/diaries/preview/media",
                    { key: media.key },
                    session
                  )
                ).source
              )
            } catch (cause) {
              setError(
                cause instanceof Error ? cause.message : "媒体预览失败。"
              )
            } finally {
              setBusy(false)
            }
          }}
        >
          {busy ? "正在加载…" : "预览媒体"}
        </Button>
      )}
      {source.startsWith("data:image/") ? (
        <img
          src={source}
          alt="日记图片"
          className="max-h-96 max-w-full rounded-lg object-contain"
        />
      ) : source.startsWith("data:video/") ? (
        <video src={source} controls className="max-h-96 max-w-full" />
      ) : source ? (
        <audio src={source} controls />
      ) : null}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

export function DiaryPreview({ session }: { session: Session }) {
  const [date, setDate] = useState(todayString)
  const [category, setCategory] = useState<DiaryType>("all")
  const [revision, setRevision] = useState(0)
  const [state, setState] = useState<State>({ key: "", loading: true })
  const key = `${date}/${category}/${revision}`
  useEffect(() => {
    let active = true
    if (!date || date > todayString()) return
    const timer = window.setTimeout(() => {
      request<Result>(
        "/diaries/preview",
        { date, diaryType: category },
        session
      )
        .then((data) => {
          if (active) setState({ key, loading: false, data })
        })
        .catch((cause) => {
          if (active)
            setState({
              key,
              loading: false,
              error:
                cause instanceof ApiError ? cause.message : "读取预览失败。",
            })
        })
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [date, category, key, session])
  const invalid = !date || date > todayString()
  const current = state.key === key ? state : { key, loading: true }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8 lg:p-12">
      <div>
        <h2 className="text-3xl font-semibold">日记预览</h2>
        <p className="mt-3 text-sm text-muted-foreground">
          按日期从 Hope 读取，不需要先下载归档，也不会自动保存日记。
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="grid gap-2 text-sm">
          预览日期
          <input
            className="h-10 rounded-lg border px-3"
            type="date"
            value={date}
            max={todayString()}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <label className="grid gap-2 text-sm">
          日记类型
          <select
            className="h-10 rounded-lg border bg-background px-3"
            value={category}
            onChange={(e) => setCategory(e.target.value as DiaryType)}
          >
            {DIARY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <Button
          variant="outline"
          onClick={() => setRevision((v) => v + 1)}
          disabled={invalid || current.loading}
        >
          刷新
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        {date} · 此处预览日记；独立时间胶囊请在“时间胶囊”页面查看。
      </p>
      <div aria-live="polite">
        {invalid ? (
          <p role="alert">请选择不晚于今天的有效日期。</p>
        ) : current.loading ? (
          <p>正在读取当天日记…</p>
        ) : current.error ? (
          <p
            role="alert"
            className="rounded-lg border border-destructive p-5 text-destructive"
          >
            {current.error}
          </p>
        ) : current.data?.diaries.length === 0 ? (
          <div className="rounded-xl border p-12 text-center">
            <p className="text-2xl">木有日记哦~</p>
            <p className="mt-3 text-muted-foreground">换一天看看吧</p>
          </div>
        ) : (
          current.data?.diaries.map((diary, index) => (
            <article
              key={`${key}/${diary.id}/${index}`}
              className="mb-5 rounded-xl border bg-card p-6"
            >
              <h3 className="text-lg font-semibold">
                {diary.note_date} ·{" "}
                {DIARY_TYPES.find((t) => t.value === diary.diary_type)?.label ||
                  "未知类型"}
              </h3>
              <p className="my-3 text-sm text-muted-foreground">
                {[
                  diary.emotion_label && `心情：${diary.emotion_label}`,
                  diary.weather_label && `天气：${diary.weather_label}`,
                ]
                  .filter(Boolean)
                  .join("　　")}
              </p>
              {diary.content.map((block, i) => (
                <div key={i}>
                  <p className="break-words whitespace-pre-wrap">
                    {block.text}
                  </p>
                  {block.media.map((media, j) => (
                    <MediaPreview
                      key={j}
                      media={media}
                      kind={block.kind}
                      session={session}
                    />
                  ))}
                </div>
              ))}
              {!diary.content.some((b) => b.text || b.media.length) && (
                <p className="break-words whitespace-pre-wrap">
                  {diary.original_text}
                </p>
              )}
              {diary.original_text_secondary && (
                <p className="mt-3 break-words whitespace-pre-wrap">
                  {diary.original_text_secondary}
                </p>
              )}
              {diary.comments.some((g) => g.items.length) && (
                <h4 className="mt-5 font-medium">留言</h4>
              )}
              {diary.comments
                .flatMap((g) => g.items)
                .map((comment, i) => (
                  <p
                    className="mt-2 text-sm break-words whitespace-pre-wrap"
                    key={i}
                  >
                    {comment.from_name || comment.author?.name || "作者未知"}
                    {comment.to_name ? ` 回复 ${comment.to_name}` : ""}：
                    {comment.text}
                  </p>
                ))}
            </article>
          ))
        )}
      </div>
    </main>
  )
}
