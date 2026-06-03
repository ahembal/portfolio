import React, { useEffect, useRef } from "react";

interface Props {
  url: string;
  onLoad: (url: string, title: string) => void;
  webviewRef: React.MutableRefObject<Electron.WebviewTag | null>;
}

export default function BrowserView({ url, onLoad, webviewRef }: Props) {
  const ref = useRef<Electron.WebviewTag>(null);

  useEffect(() => {
    if (webviewRef) webviewRef.current = ref.current;
  }, [webviewRef]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onDidNavigate = () => {
      const title = (el as unknown as { getTitle: () => string }).getTitle?.() ?? el.src;
      onLoad(el.src, title);
    };

    // Tell the main process which webview is active so the CDP server can act on it
    const onDomReady = () => {
      const id = (el as unknown as { getWebContentsId: () => number }).getWebContentsId?.();
      if (id) window.electronAPI.setActiveWebview(id);
    };

    el.addEventListener("did-navigate", onDidNavigate);
    el.addEventListener("did-navigate-in-page", onDidNavigate);
    el.addEventListener("dom-ready", onDomReady);
    return () => {
      el.removeEventListener("did-navigate", onDidNavigate);
      el.removeEventListener("did-navigate-in-page", onDidNavigate);
      el.removeEventListener("dom-ready", onDomReady);
    };
  }, [onLoad]);

  // Navigate when URL prop changes
  useEffect(() => {
    const el = ref.current;
    if (el && el.src !== url) {
      el.src = url;
    }
  }, [url]);

  return (
    <webview
      ref={ref}
      src={url}
      className="webview"
      // @ts-ignore — Electron webview attrs not in TS types
      allowpopups="true"
    />
  );
}
