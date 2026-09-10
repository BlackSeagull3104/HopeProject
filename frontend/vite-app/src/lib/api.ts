import { invoke, isTauri } from "@tauri-apps/api/core"

export type Session = { token: string; userId: string; displayName?: string }
export type Stats = { generated: number; skipped: number; failed: number }
export type Job = {
  state: "running" | "completed" | "partial" | "failed"
  stage: string
  outputDir?: string
  result?: {
    outputDir: string
    diaryCount: number
    markdown?: Stats
    export?: Stats
    format?: string
    media?: { downloaded: number; skipped: number; failed: number }
  }
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function request<T>(
  path: string,
  body?: object,
  session?: Session
): Promise<T> {
  if (isTauri()) {
    let reply: { status: number; body: T & { error?: string } }
    try {
      reply = await invoke("desktop_request", {
        path,
        body: body ?? null,
        token: session?.token ?? null,
      })
    } catch {
      throw new ApiError("桌面后端连接失败，请重新启动 Hope Archive。", 0)
    }
    if (reply.status >= 400)
      throw new ApiError(reply.body.error || "请求失败。", reply.status)
    return reply.body
  }
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Hope-Client": "react",
        ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    })
  } catch {
    throw new ApiError(
      "无法连接本地服务。请确认 Python API 已启动；请求是否完成未知，请勿立即重复提交。",
      0
    )
  }
  let data
  try {
    data = await response.json()
  } catch {
    throw new ApiError(
      "本地服务没有返回有效响应，请确认 Python API 已启动。",
      response.status
    )
  }
  if (!response.ok)
    throw new ApiError(data.error || "请求失败。", response.status)
  return data as T
}
