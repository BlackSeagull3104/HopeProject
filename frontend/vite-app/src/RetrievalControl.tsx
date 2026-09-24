import { useEffect, useState } from "react"
import { request, type Session } from "@/lib/api"
import { retrievalModes, stateLabels, working, type ComponentState, type RetrievalMode } from "@/lib/retrieval"
import { Button } from "@/components/ui/button"

type Status = { state: ComponentState; model: string; downloadBytes: number; storage: string }
export function RetrievalControl({ mode, onChange, session, disabled = false }: {
  mode: RetrievalMode; onChange: (mode: RetrievalMode) => void; session?: Session; disabled?: boolean
}) {
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)
  useEffect(() => {
    if (mode !== "Hybrid") return
    let active = true
    async function refresh() {
      try {
        const next = await request<Status>("/library/semantic/status", {}, session)
        if (active) { setStatus(next); setError("") }
      } catch { if (active) setError("无法读取语义组件状态；搜索仍可使用 FTS5。") }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [mode, session])
  async function action(name: "install" | "index" | "rebuild") {
    setPending(true); setError("")
    try { setStatus(await request<Status>(`/library/semantic/${name}`, name === "install" ? { confirmed: true } : {}, session)) }
    catch { setError("操作失败，请重试。搜索仍可使用 FTS5。") }
    finally { setPending(false) }
  }
  return <section className="space-y-3 rounded-xl border bg-muted/20 p-4">
    <label className="flex items-center gap-3 text-sm">检索模式
      <select aria-label="检索模式" className="rounded-lg border bg-background p-2" value={mode} disabled={disabled} onChange={(e) => onChange(e.target.value as RetrievalMode)}>
        {retrievalModes.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
    </label>
    <p className="text-sm text-muted-foreground">{mode === "FTS5" ? "轻量本地检索，无需额外组件。" : "FTS5 + 本地语义检索，可以更好地找到表达不同但意思相近的记录。"}</p>
    {mode === "Hybrid" && <div className="space-y-3 text-sm" aria-live="polite">
      <p>Hybrid 检索需要本地语义检索组件。仅用于日记；胶囊仍使用 FTS5。</p>
      <p>intfloat/multilingual-e5-small · 下载约 129.16 MiB · 处理在本机完成，日记文本不会上传用于 embedding。无需 API Key。</p>
      <p>存放于应用管理的本机缓存，不在日记归档或备份中。首次下载需联网，完成后可离线使用。</p>
      <p>{status ? stateLabels[status.state] : "正在读取组件状态…"}</p>
      {status && !working(status.state) && <div className="flex flex-wrap gap-2">
        {["not_installed", "download_failed", "verification_failed", "index_failed"].includes(status.state) && <Button variant="outline" disabled={pending} onClick={() => void action("install")}>下载并启用</Button>}
        {!["not_installed", "download_failed", "verification_failed"].includes(status.state) && <Button variant="outline" disabled={pending} onClick={() => void action(status.state === "index_failed" ? "rebuild" : "index")}>更新语义索引</Button>}
        {status.state === "ready" && <Button variant="ghost" disabled={pending} onClick={() => void action("rebuild")}>重建语义索引</Button>}
      </div>}
      {status?.state !== "ready" && <p>组件未就绪时使用 FTS5；不会自动下载。</p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
    </div>}
  </section>
}
