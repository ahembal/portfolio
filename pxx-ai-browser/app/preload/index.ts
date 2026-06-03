import { contextBridge, ipcRenderer } from "electron";

// Exposed to renderer as window.electronAPI — no Node access leaks into renderer
contextBridge.exposeInMainWorld("electronAPI", {
  // Send a message to a companion with current page context
  companionChat: (payload: {
    companion: string;
    message: string;
    pageContent: string;
    pageUrl: string;
  }) => ipcRenderer.send("companion:chat", payload),

  // Send a research question — delegates to p6
  companionResearch: (question: string) =>
    ipcRenderer.send("companion:research", { question }),

  // Give a goal to the acting companion — agent clicks/types/navigates
  companionAct: (goal: string) =>
    ipcRenderer.send("companion:act", { goal }),

  // Subscribe to streamed companion events
  onCompanionEvent: (callback: (data: object) => void) => {
    const handler = (_: Electron.IpcRendererEvent, data: object) => callback(data);
    ipcRenderer.on("companion:event", handler);
    return () => ipcRenderer.removeListener("companion:event", handler);
  },

  // Check backend health
  backendHealth: () => ipcRenderer.invoke("backend:health"),

  // Tell the main process which webview is active so the CDP server acts on it
  setActiveWebview: (webContentsId: number) =>
    ipcRenderer.send("webview:active", webContentsId),
});
