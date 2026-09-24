import { useEffect, useState } from "react"
import { ArchiveFolderButton } from "@/ArchiveFolderButton"
import { request, type Session } from "@/lib/api"
import { DIARY_TYPES } from "@/lib/diary"
import { presetRange, type AIMode, type DatePreset } from "@/lib/ai"
import { Button } from "@/components/ui/button"
import { RetrievalControl } from "@/RetrievalControl"
import type { RetrievalMode, RetrievalResult } from "@/lib/retrieval"

type Source = { id: string; date: string; diaryType: string; title: string; excerpt: string }
type Provider = { provider: string; label: string; model: string }
type Turn = { question: string; answer: string; sources: Source[] }
type Plan = { id: string; state: "prepared" | "running" | "completed" | "failed" | "cancelled";
  retrieval?: RetrievalResult;
  stage: string; diaryCount: number; chunkCount: number; calls: number; large: boolean;
  answer: string; sources: Source[]; error: string; truncated: boolean;
  topics: { topic: string; count: number; sources: Source[] }[] }
type Detail = { date: string; diaryType: string; title: string; body: string }
const input = "h-10 w-full rounded-lg border bg-background px-3 text-sm"
const modes: [AIMode, string][] = [["ask", "问日记"], ["review", "回顾"], ["timeline", "时间线"], ["selected", "已选日记"]]
const lenses = [["general", "综合回顾"], ["study", "学习 / 工作"], ["life", "生活"], ["travel", "旅行 / 活动"], ["topics", "反复提到的主题"], ["custom", "自定义问题"]]
const label = (value: string) => DIARY_TYPES.find((item) => item.value === value)?.label || "日记"

export function AIAssistantPage({ session, selectedIds, onSettings, onArchive }: {
  session?: Session; selectedIds: string[]; onSettings: () => void; onArchive: () => void
}) {
  const [providers, setProviders] = useState<Provider[]>([])
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>("FTS5")
  const [provider, setProvider] = useState("")
  const [mode, setMode] = useState<AIMode>(selectedIds.length ? "selected" : "ask")
  const [preset, setPreset] = useState<DatePreset>("7d")
  const [beginDate, setBegin] = useState("")
  const [endDate, setEnd] = useState("")
  const [diaryType, setDiaryType] = useState("all")
  const [lens, setLens] = useState("general")
  const [question, setQuestion] = useState("")
  const [turns, setTurns] = useState<Turn[]>([])
  const [plan, setPlan] = useState<Plan | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [showDisclosure, setShowDisclosure] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [detail, setDetail] = useState<Detail | null>(null)
  useEffect(() => {
    let active = true
    request<{ providers: Provider[] }>("/library/ai/status", {}, session)
      .then((result) => { if (active) { setProviders(result.providers); setProvider((value) => value || result.providers[0]?.provider || "") } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "无法读取 AI 配置。") })
    return () => { active = false }
  }, [session])
  useEffect(() => {
    if (plan?.state !== "running") return
    let active = true
    const timer = window.setInterval(() => {
      void request<Plan>("/library/ai/progress", { id: plan.id }, session)
        .then((value) => { if (active) setPlan(value) })
        .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "无法读取进度。") })
    }, 700)
    return () => { active = false; window.clearInterval(timer) }
  }, [plan?.id, plan?.state, session])
  const chosen = providers.find((item) => item.provider === provider)
  function changeMode(next: AIMode) {
    if (plan?.state === "running") void request("/library/ai/cancel", { id: plan.id }, session).catch(() => {})
    setMode(next); setPlan(null); setTurns([]); setQuestion(""); setDetail(null); setError(""); setMessage("")
    if (next === "review" && !beginDate && !endDate) {
      const range = presetRange("7d"); setBegin(range.beginDate); setEnd(range.endDate)
    }
  }
  async function execute() {
    if (!provider || busy) return
    setBusy(true); setError(""); setMessage(""); setDetail(null)
    try {
      if (mode === "ask") {
        const value = question.trim()
        if (!value) return
        const history = turns.slice(-2).flatMap((turn) => [
          { role: "user", content: turn.question }, { role: "assistant", content: turn.answer },
        ])
        const sourceIds = turns.at(-1)?.sources.map((source) => source.id).slice(0, 8) || []
        const result = await request<{ answer: string; sources: Source[]; retrieved: number; providerCalled: boolean; retrieval?: RetrievalResult }>(
          "/library/ai/ask", { question: value, beginDate, endDate, diaryType, provider,
            history, sourceIds, retrievalMode, disclosureAccepted: true }, session)
        setTurns((current) => [...current, { question: value, answer: result.answer, sources: result.sources }].slice(-6))
        setQuestion("")
        setMessage((result.retrieval?.fallback || "") + (result.providerCalled ? `已基于 ${result.retrieved} 篇日记回答。` : "本地检索没有找到足够证据，未调用模型。"))
      } else {
        const prepared = await request<Plan>("/library/ai/prepare", {
          mode, question, beginDate, endDate, diaryType, provider, lens, retrievalMode,
          ...(mode === "selected" ? { sourceIds: selectedIds } : {}), disclosureAccepted: true,
        }, session)
        setPlan(prepared)
        if (prepared.retrieval?.fallback) setMessage(prepared.retrieval.fallback)
        if (!prepared.large) setPlan(await request<Plan>("/library/ai/start", { id: prepared.id }, session))
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "AI 日记处理失败。") }
    finally { setBusy(false) }
  }
  async function startPlan(retry = false) {
    if (!plan) return
    setError("")
    try {
      setPlan(await request<Plan>("/library/ai/start", { id: plan.id, confirmLarge: true }, session))
      if (retry) setMessage("已从中断处重试，已完成的分组不会重复发送。")
    } catch (cause) { setError(cause instanceof Error ? cause.message : "无法开始生成。") }
  }
  async function openSource(source: Source) {
    try { setDetail(await request<Detail>("/library/search/detail", { id: source.id }, session)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "无法打开来源。") }
  }
  function sources(items: Source[]) {
    return !!items.length && <div className="space-y-2"><p className="text-sm font-medium">来源</p>{items.map((source) =>
      <button key={source.id} className="block w-full rounded-lg border p-3 text-left text-sm hover:bg-muted/50" onClick={() => void openSource(source)}>
        <span className="font-medium">{source.date || "日期未知"} · {label(source.diaryType)}</span>
        {source.title && ` · ${source.title}`}<span className="mt-1 block text-muted-foreground">{source.excerpt}</span>
      </button>)}</div>
  }
  return <main className="mx-auto max-w-5xl space-y-6 p-8">
    <h1 className="text-3xl font-semibold">AI 日记助手</h1>
    <section aria-label="AI 实验状态" className="space-y-2 rounded-xl border bg-muted/30 p-4">
      <h2 className="font-medium">🚧 AI 日记助手仍在建设中</h2>
      <p className="text-sm text-muted-foreground">当前功能仍处于实验阶段，尚未完成完整的人工测试，部分模型或功能可能无法正常使用。日记归档、搜索、OCR 与导出等基础功能不受影响。</p>
    </section>
    <p className="text-sm text-muted-foreground">从本地日记中检索、回顾与整理，回答附有可打开的来源。</p>
    <nav aria-label="AI 模式" className="flex flex-wrap gap-2">{modes.map(([value, name]) =>
      <Button key={value} disabled={busy} variant={mode === value ? "secondary" : "ghost"} onClick={() => changeMode(value)}>{name}</Button>)}</nav>
    {(mode === "ask" || mode === "timeline") && <RetrievalControl mode={retrievalMode} session={session} disabled={busy || plan?.state === "running"} onChange={(value) => { setRetrievalMode(value); setTurns([]); setPlan(null) }} />}
    {!providers.length ? <section className="rounded-xl border p-6"><p>尚未配置 AI 服务商。请先在设置中保存 API Key 与模型。</p>
      <Button className="mt-4" onClick={onSettings}>前往设置 → AI API 设置</Button></section> : <>
      <section className="grid gap-4 rounded-xl border p-5 md:grid-cols-4">
        {mode === "review" && <label className="grid gap-1 text-sm">日期快捷范围<select aria-label="日期快捷范围" className={input} value={preset} onChange={(event) => {
          const value = event.target.value as DatePreset; setPreset(value)
          if (value !== "custom") { const range = presetRange(value); setBegin(range.beginDate); setEnd(range.endDate) }
        }}><option value="7d">最近 7 天</option><option value="30d">最近 30 天</option><option value="month">本月</option><option value="previous">上月</option><option value="custom">自定义</option></select></label>}
        {mode !== "selected" && <>
          <label className="grid gap-1 text-sm">从<input aria-label="AI 开始日期" type="date" className={input} value={beginDate} max={endDate || undefined} onChange={(e) => { setBegin(e.target.value); setPreset("custom") }} /></label>
          <label className="grid gap-1 text-sm">到<input aria-label="AI 结束日期" type="date" className={input} value={endDate} min={beginDate || undefined} onChange={(e) => { setEnd(e.target.value); setPreset("custom") }} /></label>
          <label className="grid gap-1 text-sm">日记类型<select aria-label="AI 日记类型" className={input} value={diaryType} onChange={(e) => setDiaryType(e.target.value)}>{DIARY_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </>}
        <label className="grid gap-1 text-sm">当前模型<select aria-label="AI 服务商" className={input} value={provider} onChange={(e) => setProvider(e.target.value)}>{providers.map((item) => <option key={item.provider} value={item.provider}>{item.label} / {item.model}</option>)}</select></label>
      </section>
      {mode === "review" && <label className="grid max-w-xs gap-1 text-sm">回顾视角<select aria-label="回顾视角" className={input} value={lens} onChange={(e) => setLens(e.target.value)}>{lenses.map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>}
      {mode === "selected" && <p>已从本地搜索选择 {selectedIds.length} 篇日记。仅这些日记会进入 AI 上下文。</p>}
      <section className="min-h-56 space-y-5 rounded-xl border bg-card p-6" aria-live="polite">
        {mode === "ask" ? <>{!turns.length && <p className="text-muted-foreground">可以问：我最近什么时候提到过 NLP？</p>}
          {turns.map((turn, index) => <article key={index} className="space-y-3"><p><strong>你：</strong>{turn.question}</p>
            <p className="whitespace-pre-wrap"><strong>助手：</strong>{turn.answer}</p>{sources(turn.sources)}</article>)}</> : <>
          {!plan && <p className="text-muted-foreground">{mode === "review" ? "选择日期后生成有来源的日记回顾。" : mode === "timeline" ? "输入主题，按日期查看相关记录。" : selectedIds.length ? "输入问题或总结要求。" : "请先在本地搜索勾选日记。"}</p>}
          {plan && <div className="space-y-4"><p>本次整理：{plan.diaryCount} 篇日记 · {plan.chunkCount} 个片段 · 预计 {plan.calls} 次 AI 请求</p>
            {plan.truncated && <p role="status">该主题命中超过 50 篇，本次时间线只处理相关度最高的 50 篇；可缩小日期范围。</p>}
            <p>{plan.stage}</p>{plan.error && <p role="alert" className="text-destructive">{plan.error}</p>}
            {plan.state === "prepared" && plan.large && <Button onClick={() => void startPlan()}>确认发送并开始</Button>}
            {plan.state === "running" && <Button variant="outline" onClick={async () => {
              try { setPlan(await request<Plan>("/library/ai/cancel", { id: plan.id }, session)) }
              catch (cause) { setError(cause instanceof Error ? cause.message : "取消失败。") }
            }}>取消生成</Button>}
            {plan.state === "failed" && <Button onClick={() => void startPlan(true)}>重试未完成的请求</Button>}
            {plan.state === "completed" && <><p className="whitespace-pre-wrap">{plan.answer}</p>
              {!!plan.topics?.length && <div className="space-y-2"><h2 className="font-medium">有来源的重复主题</h2>{plan.topics.map((topic) => <div key={topic.topic} className="rounded-lg border p-3"><p>{topic.topic} · {topic.count} 篇（提及次数不代表重要性）</p><div className="flex flex-wrap gap-2">{topic.sources.slice(0, 5).map((source) => <button key={source.id} className="underline" onClick={() => void openSource(source)}>{source.date}</button>)}</div></div>)}</div>}
              {sources(plan.sources)}<Button variant="outline" onClick={async () => {
                try { const result = await request<{ path: string }>("/library/ai/export", { id: plan.id }, session); setMessage(`已导出 Markdown：${result.path}`) }
                catch (cause) { setError(cause instanceof Error ? cause.message : "导出失败。") }
              }}>导出 Markdown</Button></>}
          </div>}
        </>}
      </section>
      <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); if (!accepted) setShowDisclosure(true); else void execute() }}>
        {(mode === "ask" || mode === "timeline" || mode === "selected" || lens === "custom") && <input aria-label="询问本地日记" maxLength={500} className={`${input} flex-1`} placeholder={mode === "timeline" ? "输入时间线主题…" : "Ask about your archive..."} value={question} onChange={(e) => setQuestion(e.target.value)} />}
        <Button type="submit" disabled={busy || !!(mode === "selected" && !selectedIds.length) || !!((mode !== "review" || lens === "custom") && !question.trim()) || plan?.state === "running"}>{mode === "ask" ? "发送" : "读取并预估"}</Button>
      </form>
      <p className="text-xs text-muted-foreground">当前模型：{chosen?.label} / {chosen?.model}。问日记最多选择 8 个相关片段；回顾与时间线会在本机分组后逐组处理。 <button className="underline" onClick={() => setShowDisclosure(true)}>查看隐私说明</button></p>
    </>}
    {message && <><p>{message}</p><ArchiveFolderButton area="ai" /></>}{error && <p role="alert" className="text-destructive">{error}</p>}
    {detail && <section className="rounded-xl border p-6"><h2 className="text-xl font-semibold">来源详情 · {detail.date} · {label(detail.diaryType)}</h2><p className="mt-4 whitespace-pre-wrap break-words">{detail.body}</p></section>}
    <Button variant="ghost" onClick={onArchive}>前往日记归档</Button>
    {showDisclosure && <section role="dialog" aria-modal="true" aria-label="AI 隐私说明" className="fixed inset-0 z-50 grid place-items-center bg-background/95 p-8"><div className="max-w-lg space-y-5 rounded-2xl border bg-card p-8"><h2 className="text-2xl font-semibold">发送前请确认</h2>
      <p>AI 日记助手会先在本地检索相关日记，只将回答当前问题所需的相关日记片段发送给您配置的 AI 服务商。</p>
      <p>当前服务商 / 模型：{chosen?.label} / {chosen?.model}</p>
      <p>将发送：{mode === "selected" ? `${selectedIds.length} 篇您明确选择的日记` : mode === "review" ? "所选日期范围内的日记内容，较大范围可能需要多次 AI 请求" : "最多 8 个相关日记片段"}。{mode === "review" ? "不会发送范围外日记" : mode === "selected" ? "不会发送未选日记" : "不会发送完整归档"}、内部路径或 API Key。</p>
      <div className="flex gap-3"><Button onClick={() => { setAccepted(true); setShowDisclosure(false); void execute() }}>了解并继续</Button><Button variant="ghost" onClick={() => setShowDisclosure(false)}>取消</Button></div></div></section>}
  </main>
}
