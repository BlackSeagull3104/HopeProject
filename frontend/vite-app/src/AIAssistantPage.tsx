import { useEffect, useState } from "react"
import { request, type Session } from "@/lib/api"
import { DIARY_TYPES } from "@/lib/diary"
import { Button } from "@/components/ui/button"

type Provider = { provider: string; label: string; model: string; configured: boolean }
type Source = { id: string; date: string; diaryType: string; title: string; excerpt: string }
type Turn = { question: string; answer: string; sources: Source[] }
type Detail = { id: string; date: string; diaryType: string; title: string; body: string }
const input = "h-10 rounded-lg border bg-background px-3 text-sm min-w-0"

function diaryLabel(value: string) {
  return DIARY_TYPES.find((item) => item.value === value)?.label || "日记"
}

export function AIAssistantPage({ session, onSettings, onArchive }: {
  session?: Session
  onSettings: () => void
  onArchive: () => void
}) {
  const [providers, setProviders] = useState<Provider[]>([])
  const [provider, setProvider] = useState("")
  const [question, setQuestion] = useState("")
  const [beginDate, setBegin] = useState("")
  const [endDate, setEnd] = useState("")
  const [diaryType, setDiaryType] = useState("all")
  const [turns, setTurns] = useState<Turn[]>([])
  const [accepted, setAccepted] = useState(false)
  const [showDisclosure, setShowDisclosure] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState("")
  const [error, setError] = useState("")
  const [detail, setDetail] = useState<Detail | null>(null)
  useEffect(() => {
    let active = true
    request<{ providers: Provider[] }>("/library/ai/status", {}, session)
      .then((result) => {
        if (!active) return
        setProviders(result.providers)
        setProvider((current) => current || result.providers[0]?.provider || "")
      })
      .catch((cause) => active && setError(cause instanceof Error ? cause.message : "无法读取 AI 配置。"))
    return () => { active = false }
  }, [session])
  const selected = providers.find((item) => item.provider === provider)
  async function ask(disclosureOverride = false) {
    if (!accepted && !disclosureOverride) { setShowDisclosure(true); return }
    const value = question.trim()
    if (!value || !provider) return
    setBusy(true); setError(""); setDetail(null); setStage("正在检索日记…")
    try {
      const history = turns.slice(-2).flatMap((turn) => [
        { role: "user", content: turn.question },
        { role: "assistant", content: turn.answer },
      ])
      setStage("正在构建受限上下文并生成回答…")
      const result = await request<{ answer: string; sources: Source[]; retrieved: number; providerCalled: boolean }>(
        "/library/ai/ask",
        { question: value, beginDate, endDate, diaryType, provider, history, disclosureAccepted: true }, session
      )
      setTurns((current) => [...current, { question: value, answer: result.answer, sources: result.sources }].slice(-6))
      setQuestion("")
      setStage(result.providerCalled ? `已基于 ${result.retrieved} 篇本地日记生成回答。` : "本地检索没有找到足够证据，未调用模型。")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "AI 日记问答失败。")
    } finally { setBusy(false) }
  }
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <div>
        <h1 className="text-3xl font-semibold">AI 日记助手</h1>
        <p className="mt-2 text-sm text-muted-foreground">先在本地检索，再由你配置的模型依据有限日记片段回答；不是通用聊天机器人。</p>
      </div>
      {!providers.length ? (
        <section className="rounded-xl border p-6">
          <p>尚未配置 AI 服务商。请先在设置中保存 API Key 与模型。</p>
          <Button className="mt-4" onClick={onSettings}>前往设置 → AI API 设置</Button>
        </section>
      ) : (
        <>
          <section className="grid gap-4 rounded-xl border p-5 md:grid-cols-4">
            <label className="grid gap-1 text-sm">从<input aria-label="AI 开始日期" type="date" className={input} value={beginDate} max={endDate || undefined} onChange={(e) => setBegin(e.target.value)} /></label>
            <label className="grid gap-1 text-sm">到<input aria-label="AI 结束日期" type="date" className={input} value={endDate} min={beginDate || undefined} onChange={(e) => setEnd(e.target.value)} /></label>
            <label className="grid gap-1 text-sm">日记类型<select aria-label="AI 日记类型" className={input} value={diaryType} onChange={(e) => setDiaryType(e.target.value)}>{DIARY_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <label className="grid gap-1 text-sm">当前模型<select aria-label="AI 服务商" className={input} value={provider} onChange={(e) => setProvider(e.target.value)}>{providers.map((item) => <option key={item.provider} value={item.provider}>{item.label} / {item.model}</option>)}</select></label>
          </section>
          <section className="min-h-64 space-y-5 rounded-xl border bg-card p-6" aria-live="polite">
            {!turns.length && <p className="text-muted-foreground">可以问：我最近什么时候提到过 NLP？</p>}
            {turns.map((turn, index) => <article key={index} className="space-y-3">
              <p><strong>你：</strong>{turn.question}</p>
              <p className="whitespace-pre-wrap"><strong>助手：</strong>{turn.answer}</p>
              {!!turn.sources.length && <div className="space-y-2"><p className="text-sm font-medium">来源</p>{turn.sources.map((source) => <button key={source.id} className="block w-full rounded-lg border p-3 text-left text-sm hover:bg-muted/50" onClick={async () => {
                setError("")
                try { setDetail(await request<Detail>("/library/search/detail", { id: source.id }, session)) }
                catch (cause) { setError(cause instanceof Error ? cause.message : "无法打开来源。") }
              }}><span className="font-medium">{source.date || "日期未知"} · {diaryLabel(source.diaryType)}</span>{source.title && ` · ${source.title}`}<span className="mt-1 block text-muted-foreground">{source.excerpt}</span></button>)}</div>}
            </article>)}
            {busy && <p>{stage}</p>}
          </section>
          <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); void ask(false) }}>
            <input aria-label="询问本地日记" maxLength={500} className={`${input} flex-1`} placeholder="Ask about your archive..." value={question} onChange={(e) => setQuestion(e.target.value)} />
            <Button type="submit" disabled={busy || !question.trim()}>发送</Button>
          </form>
          <p className="text-xs text-muted-foreground">当前模型：{selected?.label} / {selected?.model}。每次最多选择 8 个相关片段；没有相关证据时不会调用模型。 <button className="underline" onClick={() => setShowDisclosure(true)}>查看隐私说明</button></p>
        </>
      )}
      {stage && !busy && <p>{stage}</p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      {detail && <section className="rounded-xl border p-6"><h2 className="text-xl font-semibold">来源详情 · {detail.date} · {diaryLabel(detail.diaryType)}</h2><p className="mt-4 whitespace-pre-wrap break-words">{detail.body}</p></section>}
      <Button variant="ghost" onClick={onArchive}>前往日记归档</Button>
      {showDisclosure && <section role="dialog" aria-modal="true" aria-label="AI 隐私说明" className="fixed inset-0 z-50 grid place-items-center bg-background/95 p-8"><div className="max-w-lg space-y-5 rounded-2xl border bg-card p-8"><h2 className="text-2xl font-semibold">发送前请确认</h2><p>AI 日记助手会先在本地检索相关日记，只将回答当前问题所需的相关日记片段发送给您配置的 AI 服务商。</p><p>当前模型：{selected?.label} / {selected?.model}</p><p>将发送：最多 8 个相关日记片段，不会发送完整归档、内部路径或 API Key。</p><div className="flex gap-3"><Button onClick={() => { setAccepted(true); setShowDisclosure(false); void ask(true) }}>了解并继续</Button><Button variant="ghost" onClick={() => setShowDisclosure(false)}>取消</Button></div></div></section>}
    </main>
  )
}
