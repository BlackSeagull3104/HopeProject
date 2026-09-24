export type RetrievalMode = "FTS5" | "Hybrid"
export type RetrievalResult = { mode: RetrievalMode; fallback: string }
export type ComponentState = "not_installed" | "downloading" | "verifying" | "installed" | "indexing" | "ready" | "download_failed" | "verification_failed" | "index_failed" | "rebuild_required"
export const retrievalModes: RetrievalMode[] = ["FTS5", "Hybrid"]
export const stateLabels: Record<ComponentState, string> = {
  not_installed: "尚未安装", downloading: "正在下载组件…", verifying: "正在校验组件…",
  installed: "组件已安装", indexing: "正在本机建立语义索引…", ready: "Hybrid 已就绪",
  download_failed: "下载失败，请重试。", verification_failed: "校验失败，组件未启用，请重新下载。",
  index_failed: "语义索引或运行时不可用，请重建或重新下载组件。", rebuild_required: "索引需要更新或重建。",
}
export const working = (state: ComponentState) => ["downloading", "verifying", "indexing"].includes(state)
