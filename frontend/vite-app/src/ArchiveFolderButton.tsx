import { useState } from "react"
import { request } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function ArchiveFolderButton({ area = "diaries" }: { area?: "diaries" | "ocr" | "capsules" | "ai" }) {
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  return <div className="space-y-2">
    <Button variant="outline" disabled={busy} onClick={async () => {
      setBusy(true); setError("")
      try { await request("/settings/open-archive", { area }) }
      catch (cause) { setError(cause instanceof Error ? cause.message : "无法打开归档文件夹。") }
      finally { setBusy(false) }
    }}>打开归档文件夹</Button>
    {error && <p role="alert">{error}</p>}
  </div>
}
