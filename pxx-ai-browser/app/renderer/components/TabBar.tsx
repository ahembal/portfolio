import React, { useState, KeyboardEvent } from "react";
import { Tab } from "../App";

interface Props {
  tabs: Tab[];
  activeTabId: string;
  onSelect: (id: string) => void;
  onAdd: () => void;
  onClose: (id: string) => void;
  onNavigate: (url: string) => void;
  currentUrl: string;
  onTogglePanel: () => void;
  panelOpen: boolean;
}

export default function TabBar({
  tabs, activeTabId, onSelect, onAdd, onClose,
  onNavigate, currentUrl, onTogglePanel, panelOpen,
}: Props) {
  const [addressBar, setAddressBar] = useState(currentUrl);

  const commit = () => {
    let url = addressBar.trim();
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      url = url.includes(".") ? `https://${url}` : `https://www.google.com/search?q=${encodeURIComponent(url)}`;
    }
    onNavigate(url);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") commit();
  };

  return (
    <div className="tabbar">
      <div className="tabs">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={`tab ${tab.id === activeTabId ? "tab--active" : ""}`}
            onClick={() => onSelect(tab.id)}
          >
            <span className="tab__title">{tab.title || "New Tab"}</span>
            <button
              className="tab__close"
              onClick={(e) => { e.stopPropagation(); onClose(tab.id); }}
            >
              ×
            </button>
          </div>
        ))}
        <button className="tab-add" onClick={onAdd}>+</button>
      </div>
      <div className="toolbar">
        <input
          className="address-bar"
          value={addressBar}
          onChange={(e) => setAddressBar(e.target.value)}
          onKeyDown={onKey}
          onFocus={(e) => e.target.select()}
          spellCheck={false}
        />
        <button
          className={`companion-toggle ${panelOpen ? "companion-toggle--active" : ""}`}
          onClick={onTogglePanel}
          title="Toggle AI Companion"
        >
          ✦
        </button>
      </div>
    </div>
  );
}
