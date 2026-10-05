export type Task = {
  id: string;
  user_message: string;
  state: string;
  final_response: string | null;
  cancel_requested: boolean;
  tool_calls: Array<Record<string, unknown>>;
  approvals: Array<Record<string, unknown>>;
  audit: Array<Record<string, unknown>>;
};

export type TaskEvent = {
  id: number;
  task_id: string;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type Memory = { id: string; content: string; tags: string[]; created_at: string; updated_at: string };
export type AppSettings = { gemini_model: string; agent_max_steps: number; default_terminal: string; browser_enabled: boolean; allowed_roots: string[]; confirmation_behavior: string; log_retention_days: number; memory_enabled: boolean; computer_use_enabled: boolean };

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const sessionToken = import.meta.env.VITE_API_SESSION_TOKEN ?? "";

function headers(extra: Record<string, string> = {}): HeadersInit {
  return { Authorization: `Bearer ${sessionToken}`, ...extra };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { ...init, headers: headers((init.headers ?? {}) as Record<string, string>) });
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}

export function sendChat(message: string) { return request<{ task_id: string }>("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) }); }
export function listTasks() { return request<Task[]>("/api/tasks"); }
export function getTask(taskId: string) { return request<Task>(`/api/tasks/${taskId}`); }
export function cancelTask(taskId: string) { return request<Task>(`/api/tasks/${taskId}/cancel`, { method: "POST" }); }
export function resolveApproval(approvalId: string, decision: "approve" | "reject") { return request<{ approval_id: string }>(`/api/approvals/${approvalId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) }); }
export function listMemory() { return request<Memory[]>("/api/memory"); }
export function createMemory(content: string) { return request<Memory>("/api/memory", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) }); }
export function deleteMemory(id: string) { return request<{ id: string }>(`/api/memory/${id}`, { method: "DELETE" }); }
export function getSettings() { return request<AppSettings>("/api/settings"); }
export function updateSettings(changes: Partial<AppSettings>) { return request<AppSettings>("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) }); }

export async function streamTaskEvents(taskId: string, lastEventId: number, onEvent: (event: TaskEvent) => void, signal: AbortSignal): Promise<boolean> {
  const response = await fetch(`${apiBase}/api/tasks/${taskId}/events`, { headers: headers({ "Last-Event-ID": String(lastEventId) }), signal });
  if (!response.ok || !response.body) throw new Error(`${response.status}: unable to open event stream`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  while (true) {
    const read = await reader.read();
    if (read.done) break;
    buffer += decoder.decode(read.value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
      if (!data) continue;
      const event = JSON.parse(data) as TaskEvent;
      onEvent(event);
      terminal = ["task_completed", "task_failed", "task_cancelled"].includes(event.type);
    }
  }
  return terminal;
}
