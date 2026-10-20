import { useEffect, useRef, useState } from "react"
import { request } from "@/lib/api"
import { Button } from "@/components/ui/button"

type RuntimeStatus = {
  state: string; installed: boolean; available: boolean
  downloadBytes: number | null; diskBytes: number | null; receivedBytes: number
}
const size = (bytes: number | null) => bytes === null ? "待发布" : `${(bytes / 1048576).toFixed(1)} MiB`
const working = (s: RuntimeStatus | null) => !!s && ["downloading", "verifying", "cancelling"].includes(s.state)

export function useRuntimeInstall() {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<RuntimeStatus | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const action = useRef<(() => void) | null>(null)
  const mounted = useRef(true)
  const epoch = useRef(0)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; action.current = null }
  }, [])
  async function ensure(next: () => void) {
    const attempt = ++epoch.current
    setError("")
    try {
      const result = await request<RuntimeStatus>("/components/runtime/status", {})
      if (!mounted.current || attempt !== epoch.current) return
      if (result.installed && !working(result)) { next(); return }
      action.current = next
      setStatus(result); setOpen(true)
    } catch {
      if (mounted.current) { setOpen(true); setError("无法读取组件状态，请稍后重试。") }
    }
  }
  useEffect(() => {
    if (!open) return
    let active = true
    const timer = window.setInterval(() => {
      void request<RuntimeStatus>("/components/runtime/status", {}).then(next => {
        if (active) setStatus(next)
      }).catch(() => { if (active) setError("无法读取安装进度，请稍后重试。") })
    }, 750)
    return () => { active = false; window.clearInterval(timer) }
  }, [open])
  async function install() {
    setBusy(true); setError("")
    try { setStatus(await request<RuntimeStatus>("/components/runtime/install", { confirmed: true })) }
    catch { setError("安装未完成，请检查网络、磁盘空间后重试。") }
    finally { if (mounted.current) setBusy(false) }
  }
  async function cancel() {
    epoch.current++; action.current = null
    try {
      if (working(status)) await request("/components/runtime/cancel", {})
      setOpen(false)
    } catch { setError("未能取消安装，请重试。") }
  }
  const panel = open && <section role="dialog" aria-label="安装本地识别组件" aria-modal="false" className="space-y-3 rounded-xl border p-4">
    <h3 className="font-semibold">安装本地识别组件？</h3>
    <p>OCR 与语义检索共用，安装一次即可。下载约 {size(status?.downloadBytes ?? null)}，解压占用约 {size(status?.diskBytes ?? null)}。安装后可离线使用；语义检索还需单独安装语义模型。</p>
    <p>不下载日记或上传图片。取消不影响预览、归档、导出和关键词搜索。</p>
    {status && !status.available && <p>此版本的组件下载包尚未发布，请继续使用其他功能。</p>}
    {working(status) && <p aria-live="polite">{status?.state === "verifying" ? "正在校验组件…" : status?.state === "cancelling" ? "正在取消…" : `正在下载：${size(status?.receivedBytes ?? 0)}`}</p>}
    {status?.state === "failed" && <p role="alert">安装失败，未启用组件；可重试。</p>}
    {error && <p role="alert">{error}</p>}
    <div className="flex gap-2">
      {status?.installed && !working(status)
        ? <Button onClick={() => { const next = action.current; action.current = null; setOpen(false); next?.() }}>继续使用</Button>
        : <Button disabled={busy || working(status) || !status?.available} onClick={() => void install()}>确认下载并安装</Button>}
      <Button variant="outline" disabled={busy} onClick={() => void cancel()}>取消</Button>
    </div>
  </section>
  return { ensure, panel }
}
