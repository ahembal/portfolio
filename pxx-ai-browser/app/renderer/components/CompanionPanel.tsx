import React, { useState } from "react";
import CompanionChat from "./CompanionChat";

type CompanionId = "docs" | "research" | "github" | "act";

const COMPANIONS: { id: CompanionId; label: string; description: string }[] = [
  { id: "docs", label: "Docs", description: "Ask anything about the current page" },
  { id: "act", label: "Act", description: "Give a goal — the agent clicks, types, and navigates for you" },
  { id: "research", label: "Research", description: "Deep research via PubMed, UniProt, RAG (p6)" },
  { id: "github", label: "GitHub", description: "Understand repos, issues, and PRs" },
];

interface Props {
  currentUrl: string;
  getPageContent: () => Promise<string>;
}

export default function CompanionPanel({ currentUrl, getPageContent }: Props) {
  const [active, setActive] = useState<CompanionId>("docs");

  const companion = COMPANIONS.find((c) => c.id === active)!;

  return (
    <div className="companion-panel">
      <div className="companion-panel__header">
        <div className="companion-tabs">
          {COMPANIONS.map((c) => (
            <button
              key={c.id}
              className={`companion-tab ${c.id === active ? "companion-tab--active" : ""}`}
              onClick={() => setActive(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>
        <p className="companion-description">{companion.description}</p>
      </div>
      <CompanionChat
        key={active}
        companionId={active}
        currentUrl={currentUrl}
        getPageContent={getPageContent}
      />
    </div>
  );
}
