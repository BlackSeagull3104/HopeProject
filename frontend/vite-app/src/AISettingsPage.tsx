import { useEffect, useState } from "react"
import { request } from "@/lib/api"
import { Button } from "@/components/ui/button"

type Preset = {
  id: string
  label: string
  baseUrl: string
  models: string[]
  discovery?: boolean
}
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
  const [editingKey, setEditingKey] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(true)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [custom, setCustom] = useState(!preset.models.length)
  const [discovered, setDiscovered] = useState<string[]>([])
  useEffect(() => {
    let active = true
    request<Metadata>("/ai/status", { provider: preset.id })
      .then((data) => {
        if (active) {
          setModel(data.model)
          setCustom(!preset.models.includes(data.model))
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
  }, [preset.id, preset.models])
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
        setEditingKey(false)
        setConfirmDelete(false)
        if (action === "delete") {
          setModel(result.model)
          setCustom(!preset.models.includes(result.model))
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
          模型
          <select
            aria-label="模型"
            className={input}
            value={custom ? "__custom__" : model}
            onChange={(e) => {
              const next = e.target.value
              setCustom(next === "__custom__")
              if (next !== "__custom__") setModel(next)
            }}
          >
            {!!discovered.length && (
              <optgroup label="账户可用模型">
                {discovered.map((id) => <option key={id} value={id}>{id}</option>)}
              </optgroup>
            )}
            <optgroup label="常用预设">
              {preset.models.filter((id) => !discovered.includes(id)).map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </optgroup>
            <option value="__custom__">自定义模型 ID…</option>
          </select>
        </label>
        {custom && (
          <label className="grid gap-2 text-sm">
            自定义模型 ID
            <input aria-label="自定义模型 ID" className={input} value={model}
              onChange={(e) => setModel(e.target.value)} spellCheck={false} />
          </label>
        )}
        <p className="text-xs text-muted-foreground">
          配置密钥后可刷新账户可用模型。预设不代表账户已开通；所有服务商均可填写自定义模型 ID。
        </p>
        {configured && !editingKey && <Button variant="outline" onClick={() => setEditingKey(true)}>替换 API Key</Button>}
        {(!configured || editingKey) && <label className="grid gap-2 text-sm">
          API Key
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            className={input}
            placeholder={
              "输入你自己的 API Key"
            }
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        </label>}
        {editingKey && <Button variant="ghost" onClick={() => { setKey(""); setEditingKey(false) }}>取消替换</Button>}
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            disabled={preset.discovery === false || (!configured && !key.trim())}
            onClick={async () => {
              setBusy(true)
              setError("")
              setMessage("")
              const apiKey = key
              try {
                const result = await request<{ models: string[] }>(
                  "/ai/models",
                  { provider: preset.id, baseUrl, model, apiKey }
                )
                setDiscovered(result.models)
                setMessage(
                  `发现 ${result.models.length} 个模型，可在模型名称中选择。`
                )
              } catch (cause) {
                setError(
                  cause instanceof Error ? cause.message : "模型发现失败。"
                )
              } finally {
                setBusy(false)
              }
            }}
          >
            刷新模型列表
          </Button>
          <Button
            variant="outline"
            disabled={preset.discovery === false || (!configured && !key.trim())}
            onClick={() => void act("test")}
          >
            测试连接
          </Button>
          <Button disabled={(!configured || editingKey) && !key.trim()} onClick={() => void act("save")}>保存</Button>
          <Button
            variant="outline"
            disabled={!configured}
            onClick={() => setConfirmDelete(true)}
          >
            删除 API Key
          </Button>
        </div>
        {confirmDelete && <section aria-label="确认删除密钥" className="space-y-3">
          <p>删除后此服务商将无法生成回答，其他服务商不受影响。</p>
          <Button onClick={() => void act("delete")}>确认删除 API Key</Button>
          <Button variant="ghost" onClick={() => setConfirmDelete(false)}>取消删除</Button>
        </section>}
      </fieldset>
      <p className="text-xs text-muted-foreground">
        {preset.discovery === false &&
          "此服务商暂不提供列表发现与只读连接测试，请使用预设或官方控制台的模型 / 接入点 ID。"}
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
      <h1 className="text-3xl font-semibold">AI API 设置</h1>
      <p className="text-sm leading-6 text-muted-foreground">
        使用你自己的第三方模型 API Key。本机 Windows
        凭据管理器保存密钥，调用时只发送到所选服务商。问日记模式先在本机检索，每次最多发送 8
        个相关片段；回顾和时间线按所选范围分批处理，已选日记模式只处理明确勾选的条目。较大回顾会先显示篇数与预计请求数并再次确认。不会发送内部文件路径或 API
        Key。Hope Archive 不运营中转 AI 服务器。
      </p>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <label className="grid gap-2 text-sm">
        服务商
        <select
          aria-label="服务商"
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
