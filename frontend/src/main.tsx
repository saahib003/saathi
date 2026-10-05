import { FormEvent, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { cancelTask, createMemory, deleteMemory, getSettings, getTask, listMemory, listTasks, Memory, resolveApproval, sendChat, streamTaskEvents, Task, TaskEvent, AppSettings, updateSettings } from "./services/api";
import "./styles.css";

function App() {
  const [message, setMessage] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [approval, setApproval] = useState<TaskEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [memoryText, setMemoryText] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const cursorRef = useRef(0);

  useEffect(() => { void refreshTasks(); void refreshMemory(); void getSettings().then(setSettings).catch((cause) => setError(String(cause))); return () => abortRef.current?.abort(); }, []);

  async function refreshTasks() {
    try { setTasks(await listTasks()); } catch (cause) { setError(String(cause)); }
  }

  async function refreshMemory() { try { setMemories(await listMemory()); } catch (cause) { setError(String(cause)); } }

  async function addMemory() {
    if (!memoryText.trim()) return;
    try { await createMemory(memoryText.trim()); setMemoryText(""); await refreshMemory(); } catch (cause) { setError(String(cause)); }
  }

  async function saveSettings(changes: Partial<AppSettings>) { try { setSettings(await updateSettings(changes)); } catch (cause) { setError(String(cause)); } }

  async function selectTask(taskId: string) {
    try {
      const task = await getTask(taskId);
      setSelected(task); setEvents([]); setApproval(null); cursorRef.current = 0;
      connect(taskId);
    } catch (cause) { setError(String(cause)); }
  }

  function connect(taskId: string) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const loop = async () => {
      while (!controller.signal.aborted) {
        try {
          setConnected(true);
          const terminal = await streamTaskEvents(taskId, cursorRef.current, (event) => {
            cursorRef.current = event.id;
            setEvents((current) => [...current, event]);
            if (event.type === "approval_required") setApproval(event);
            if (event.type === "approval_resolved") setApproval(null);
            void getTask(taskId).then(setSelected).then(refreshTasks);
          }, controller.signal);
          setConnected(false);
          if (terminal) return;
        } catch (cause) {
          if (controller.signal.aborted) return;
          setConnected(false); setError(String(cause));
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    };
    void loop();
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    try {
      setError(null);
      const created = await sendChat(message.trim());
      setMessage("");
      await refreshTasks();
      await selectTask(created.task_id);
    } catch (cause) { setError(String(cause)); }
  }

  async function decide(decision: "approve" | "reject") {
    if (!approval) return;
    try { await resolveApproval(String(approval.payload.approval_id), decision); setApproval(null); } catch (cause) { setError(String(cause)); }
  }

  async function cancel() {
    if (!selected) return;
    try { setSelected(await cancelTask(selected.id)); } catch (cause) { setError(String(cause)); }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <p className="eyebrow">LOCAL LAPTOP AGENT</p>
        <h1>Tasks</h1>
        <button className="new-task" onClick={() => { setSelected(null); setEvents([]); }}>+ New task</button>
        <div className="task-list">{tasks.map((task) => <button className={`task-row ${selected?.id === task.id ? "selected" : ""}`} key={task.id} onClick={() => void selectTask(task.id)}><span>{task.user_message}</span><small>{task.state}</small></button>)}</div>
        <section className="memory-panel"><span className="eyebrow">MEMORY</span><input value={memoryText} onChange={(event) => setMemoryText(event.target.value)} placeholder="Remember a fact..." onKeyDown={(event) => { if (event.key === "Enter") void addMemory(); }} />{memories.map((memory) => <div className="memory-row" key={memory.id}><span>{memory.content}</span><button onClick={() => void deleteMemory(memory.id).then(refreshMemory)}>×</button></div>)}</section>
        {settings && <section className="settings-panel"><span className="eyebrow">SETTINGS</span><label>Gemini model<input value={settings.gemini_model} onChange={(event) => setSettings({ ...settings, gemini_model: event.target.value })} onBlur={() => void saveSettings({ gemini_model: settings.gemini_model })} /></label><label>Max steps<input type="number" min="1" max="100" value={settings.agent_max_steps} onChange={(event) => setSettings({ ...settings, agent_max_steps: Number(event.target.value) })} onBlur={() => void saveSettings({ agent_max_steps: settings.agent_max_steps })} /></label><label className="check"><input type="checkbox" checked={settings.memory_enabled} onChange={(event) => void saveSettings({ memory_enabled: event.target.checked })} /> Memory enabled</label><label className="check"><input type="checkbox" checked={settings.browser_enabled} onChange={(event) => void saveSettings({ browser_enabled: event.target.checked })} /> Browser enabled</label><label className="check"><input type="checkbox" checked={settings.computer_use_enabled} onChange={(event) => void saveSettings({ computer_use_enabled: event.target.checked })} /> Computer Use enabled</label></section>}
      </aside>
      <section className="workspace">
        <header className="topbar"><div><h2>{selected?.user_message ?? "What should I help you do?"}</h2><p>{connected ? "Live updates connected" : "Event stream disconnected"}</p></div>{selected && !["COMPLETED", "FAILED", "CANCELLED"].includes(selected.state) && <button className="cancel" onClick={() => void cancel()}>Cancel</button>}</header>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="timeline">{events.length === 0 && <div className="empty">Submit a request to start an agent task.</div>}{events.map((event) => <article className="event" key={event.id}><span className="event-type">{event.type}</span><pre>{JSON.stringify(event.payload, null, 2)}</pre></article>)}</div>
        {selected && selected.audit.length > 0 && <section className="trace"><div className="trace-heading"><span className="eyebrow">AUDIT TRACE</span><strong>{selected.audit.length} records</strong></div>{selected.audit.map((entry) => <article className="trace-row" key={String(entry.id)}><div><strong>{String(entry.kind)}</strong><small>{String(entry.status)} · {String(entry.duration_ms ?? 0)} ms</small></div><pre>{JSON.stringify(entry.data, null, 2)}</pre></article>)}</section>}
        {approval && <div className="approval"><div><strong>Approval required</strong><p>{String(approval.payload.tool)} needs permission.</p><pre>{JSON.stringify(approval.payload.arguments, null, 2)}</pre></div><div className="approval-actions"><button onClick={() => void decide("approve")}>Approve</button><button className="reject" onClick={() => void decide("reject")}>Reject</button></div></div>}
        <form className="composer" onSubmit={(event) => void submit(event)}><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask the agent to do something on your laptop" /><button type="submit">Send</button></form>
      </section>
    </main>
  );
}

export default App;

createRoot(document.getElementById("root")!).render(<App />);
