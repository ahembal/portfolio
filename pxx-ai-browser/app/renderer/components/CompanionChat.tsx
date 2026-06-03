import React, { useState, useEffect, useRef, useCallback } from "react";

interface Message {
  role: "user" | "assistant" | "tool";
  content: string;
  tool?: string;
}

interface Props {
  companionId: string;
  currentUrl: string;
  getPageContent: () => Promise<string>;
}

declare global {
  interface Window {
    electronAPI: {
      companionChat: (payload: {
        companion: string;
        message: string;
        pageContent: string;
        pageUrl: string;
      }) => void;
      companionResearch: (question: string) => void;
      companionAct: (goal: string) => void;
      onCompanionEvent: (cb: (data: unknown) => void) => () => void;
      backendHealth: () => Promise<{ status: string }>;
      setActiveWebview: (id: number) => void;
    };
  }
}

export default function CompanionChat({ companionId, currentUrl, getPageContent }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Register SSE listener once
  useEffect(() => {
    const unsub = window.electronAPI.onCompanionEvent((raw) => {
      const data = raw as { type: string; tool?: string; args?: object; content?: string; message?: string; citations?: unknown[] };

      if (data.type === "tool_call") {
        setMessages((prev) => [
          ...prev,
          { role: "tool", content: `Calling ${data.tool}…`, tool: data.tool },
        ]);
      } else if (data.type === "tool_result") {
        setMessages((prev) =>
          prev.map((m, i) =>
            i === prev.length - 1 && m.tool === data.tool
              ? { ...m, content: `${data.tool}: ${(data.content ?? "").slice(0, 200)}…` }
              : m
          )
        );
      } else if (data.type === "answer") {
        setMessages((prev) => [...prev, { role: "assistant", content: data.content ?? "" }]);
      } else if (data.type === "error") {
        setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${data.message}` }]);
        setStreaming(false);
      } else if (data.type === "done") {
        setStreaming(false);
      }
    });
    unsubRef.current = unsub;
    return () => unsub();
  }, []);

  const send = useCallback(async () => {
    const q = input.trim();
    if (!q || streaming) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setStreaming(true);

    if (companionId === "research") {
      window.electronAPI.companionResearch(q);
    } else if (companionId === "act") {
      window.electronAPI.companionAct(q);
    } else {
      const pageContent = await getPageContent().catch(() => "");
      window.electronAPI.companionChat({
        companion: companionId,
        message: q,
        pageContent,
        pageUrl: currentUrl,
      });
    }
  }, [input, streaming, companionId, currentUrl, getPageContent]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="companion-chat">
      <div className="companion-chat__messages">
        {messages.length === 0 && (
          <p className="companion-chat__empty">Ask me anything about this page.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message--${m.role}`}>
            {m.role === "tool" && <span className="message__tool-badge">tool</span>}
            <span className="message__content">{m.content}</span>
          </div>
        ))}
        {streaming && <div className="message message--assistant message--streaming">…</div>}
        <div ref={bottomRef} />
      </div>
      <div className="companion-chat__input-row">
        <textarea
          className="companion-chat__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask a question…"
          rows={2}
          disabled={streaming}
        />
        <button className="companion-chat__send" onClick={send} disabled={streaming || !input.trim()}>
          {streaming ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
