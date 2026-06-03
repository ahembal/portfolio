import React, { useState, useRef, useCallback } from "react";
import TabBar from "./components/TabBar";
import BrowserView from "./components/BrowserView";
import CompanionPanel from "./components/CompanionPanel";
import "./styles/app.css";

export interface Tab {
  id: string;
  url: string;
  title: string;
  favicon?: string;
}

function makeTab(url = "https://docs.python.org/3/"): Tab {
  return { id: crypto.randomUUID(), url, title: "New Tab" };
}

export default function App() {
  const [tabs, setTabs] = useState<Tab[]>([makeTab()]);
  const [activeTabId, setActiveTabId] = useState<string>(tabs[0].id);
  const [panelOpen, setPanelOpen] = useState(true);
  const webviewRef = useRef<Electron.WebviewTag | null>(null);

  const activeTab = tabs.find((t) => t.id === activeTabId) ?? tabs[0];

  const addTab = useCallback(() => {
    const t = makeTab("https://docs.python.org/3/");
    setTabs((prev) => [...prev, t]);
    setActiveTabId(t.id);
  }, []);

  const closeTab = useCallback((id: string) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.id !== id);
      if (next.length === 0) return [makeTab()];
      return next;
    });
    setActiveTabId((prev) => {
      if (prev !== id) return prev;
      const idx = tabs.findIndex((t) => t.id === id);
      const fallback = tabs[Math.max(0, idx - 1)];
      return fallback?.id ?? tabs[0].id;
    });
  }, [tabs]);

  const navigate = useCallback((url: string) => {
    setTabs((prev) =>
      prev.map((t) => (t.id === activeTabId ? { ...t, url } : t))
    );
  }, [activeTabId]);

  const onPageLoad = useCallback((url: string, title: string) => {
    setTabs((prev) =>
      prev.map((t) => (t.id === activeTabId ? { ...t, url, title } : t))
    );
  }, [activeTabId]);

  return (
    <div className="app">
      <TabBar
        tabs={tabs}
        activeTabId={activeTabId}
        onSelect={setActiveTabId}
        onAdd={addTab}
        onClose={closeTab}
        onNavigate={navigate}
        currentUrl={activeTab.url}
        onTogglePanel={() => setPanelOpen((v) => !v)}
        panelOpen={panelOpen}
      />
      <div className="browser-area">
        <BrowserView
          key={activeTab.id}
          url={activeTab.url}
          onLoad={onPageLoad}
          webviewRef={webviewRef}
        />
        {panelOpen && (
          <CompanionPanel
            currentUrl={activeTab.url}
            getPageContent={() =>
              webviewRef.current
                ? webviewRef.current.executeJavaScript(
                    "document.body.innerText.slice(0, 8000)"
                  )
                : Promise.resolve("")
            }
          />
        )}
      </div>
    </div>
  );
}
