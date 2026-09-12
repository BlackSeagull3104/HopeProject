import { useEffect, useState } from "react"
import { request } from "@/lib/api"
import { Button } from "@/components/ui/button"

type Preset = { id: string; label: string; baseUrl: string; models: string[] }
type Metadata = {
  provider: string
  configured: boolean
  model: string
  baseUrl: string
}
const input = "h-10 w-full rounded-lg border bg-background px-3 text-sm"
function ProviderForm({ preset }: { preset: Preset }) {
  const [model, setModel] = useState(preset.models[0] || "")
  const [baseUrl, setBase] = useState(preset.baseUrl)
  const [key, setKey] = useState("")
  const [configured, setConfigured] = useState(false)
  const [busy, setBusy] = useState(true)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  useEffect(() => {
    let active = true
    request<Metadata>("/ai/status", { provider: preset.id })
      .then((data) => {
        if (active) {
          setModel(data.model)
          setBase(data.baseUrl)
          setConfigured(data.configured)
        }
      })
      .catch((cause) => {
        if (active)
          setError(
            cause instanceof Error ? cause.message : "无法读取安全配置。"
          )
      })
      .finally(() => {
        if (active) setBusy(false)
      })
    return () => {
      active = false
    }
  }, [preset.id])
  async function act(action: "save" | "test" | "delete") {
    setBusy(true)
    setError("")
    setMessage("")
    const body =
      action === "delete"
        ? { provider: preset.id }
        : { provider: preset.id, model, baseUrl, apiKey: key }
    setKey("")
    try {
      const result = await request<Metadata & { message?: string }>(
        `/ai/${action}`,
        body
      )
      if (action !== "test") {
        setConfigured(result.configured)
        if (action === "delete") {
          setModel(result.model)
          setBase(result.baseUrl)
        }
      }
      setMessage(
        action === "test"
          ? result.message || "连接测试完成。"
          : action === "save"
            ? "已保存到 Windows 凭据管理器。"
            : "已删除此服务商的密钥和配置。"
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败。")
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="space-y-5">
      <p className="text-sm">
        {busy
          ? "正在处理…"
          : configured
            ? "已配置（不会显示已保存的密钥）"
            : "未配置 API Key"}
      </p>
      <fieldset disabled={busy} className="space-y-4">
        {preset.id === "custom" && (
          <label className="grid gap-2 text-sm">
            API Base URL
            <input
              className={input}
              placeholder="https://your-provider.example/v1"
              value={baseUrl}
              onChange={(e) => setBase(e.target.value)}
            />
          </label>
        )}
        <label className="grid gap-2 text-sm">
          模型名称
          <input
            className={input}
            list="ai-model-presets"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <datalist id="ai-model-presets">
            {preset.models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </label>
        <p className="text-xs text-muted-foreground">
          可选择预设或直接输入新模型名称，是否可用以服务商账户权限为准。
        </p>
        <label className="grid gap-2 text-sm">
          API Key
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            className={input}
            placeholder={
              configured ? "留空保留；输入新值可替换" : "输入你自己的 API Key"
            }
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => void act("test")}>
            测试连接
          </Button>
          <Button onClick={() => void act("save")}>保存</Button>
          <Button
            variant="outline"
            disabled={!configured}
            onClick={() => void act("delete")}
          >
            删除 API Key
          </Button>
        </div>
      </fieldset>
      <p className="text-xs text-muted-foreground">
        测试仅读取所选服务商的模型列表，不发送日记、不调用生成。测试不会自动保存新密钥。
      </p>
      <div aria-live="polite">
        {error ? (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        ) : (
          <p>{message}</p>
        )}
      </div>
    </div>
  )
}
export function AISettingsPage() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [selected, setSelected] = useState("openai")
  const [error, setError] = useState("")
  useEffect(() => {
    let active = true
    request<{ presets: Preset[] }>("/ai/presets", {})
      .then((data) => {
        if (active) setPresets(data.presets)
      })
      .catch((cause) => {
        if (active)
          setError(cause instanceof Error ? cause.message : "加载失败。")
      })
    return () => {
      active = false
    }
  }, [])
  const preset = presets.find((p) => p.id === selected)
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-8">
      <h1 className="text-3xl font-semibold">AI 设置</h1>
      <p className="text-sm leading-6 text-muted-foreground">
        使用你自己的第三方模型 API Key。本机 Windows
        凭据管理器保存密钥，调用时只发送到所选服务商。未来分析会将所选日记内容发送至该服务商；Hope
        Archive 不运营中转 AI 服务器。本版本仅提供配置和连接测试。
      </p>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <label className="grid gap-2 text-sm">
        服务商
        <select
          className={input}
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {preset && <ProviderForm key={preset.id} preset={preset} />}
    </main>
  )
}
