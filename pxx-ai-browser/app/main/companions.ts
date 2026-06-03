import { IpcMain } from "electron";
import * as http from "http";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

/**
 * Streams SSE from the backend and forwards events over IPC to the renderer.
 * Each chunk is sent as { type, ...payload } matching the backend event schema.
 */
function streamFromBackend(
  path: string,
  params: Record<string, string>,
  onEvent: (data: object) => void,
  onDone: () => void,
  onError: (msg: string) => void
): void {
  const query = new URLSearchParams(params).toString();
  const url = new URL(`${BACKEND_URL}${path}?${query}`);

  const req = http.get(url, (res) => {
    let buffer = "";
    res.on("data", (chunk: Buffer) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const payload = JSON.parse(line.slice(6));
            onEvent(payload);
            if (payload.type === "done") onDone();
            if (payload.type === "error") onError(payload.message ?? "unknown error");
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    });
    res.on("end", onDone);
    res.on("error", (e) => onError(e.message));
  });

  req.on("error", (e) => onError(e.message));
}

export function registerCompanionHandlers(ipcMain: IpcMain): void {
  // Chat with a companion — page content + user message → streamed reply
  ipcMain.on(
    "companion:chat",
    (event, { companion, message, pageContent, pageUrl }: {
      companion: string;
      message: string;
      pageContent: string;
      pageUrl: string;
    }) => {
      streamFromBackend(
        "/chat/stream",
        { companion, message, page_url: pageUrl, page_content: pageContent.slice(0, 8000) },
        (data) => event.sender.send("companion:event", data),
        () => {},
        (msg) => event.sender.send("companion:event", { type: "error", message: msg })
      );
    }
  );

  // Research companion — delegates to p6
  ipcMain.on("companion:research", (event, { question }: { question: string }) => {
    streamFromBackend(
      "/research/stream",
      { question },
      (data) => event.sender.send("companion:event", data),
      () => {},
      (msg) => event.sender.send("companion:event", { type: "error", message: msg })
    );
  });

  // Acting companion — goal-driven browser automation via CDP bridge
  ipcMain.on("companion:act", (event, { goal }: { goal: string }) => {
    streamFromBackend(
      "/act/stream",
      { goal },
      (data) => event.sender.send("companion:event", data),
      () => {},
      (msg) => event.sender.send("companion:event", { type: "error", message: msg })
    );
  });

  // Health check
  ipcMain.handle("backend:health", async () => {
    return new Promise((resolve) => {
      http.get(`${BACKEND_URL}/health`, (res) => {
        let body = "";
        res.on("data", (c: Buffer) => (body += c.toString()));
        res.on("end", () => {
          try { resolve(JSON.parse(body)); }
          catch { resolve({ status: "error" }); }
        });
      }).on("error", () => resolve({ status: "unreachable" }));
    });
  });
}
