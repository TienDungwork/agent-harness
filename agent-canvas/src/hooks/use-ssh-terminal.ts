import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import React from "react";
import { infraSshWsUrl } from "#/api/infra/ssh";

type Status = "connecting" | "ready" | "error" | "closed";

type Options = {
  fontSize?: number;
};

export function useSshTerminal(
  serverId: string | null,
  options: Options = {},
) {
  const fontSize = options.fontSize ?? 13;
  const fontSizeRef = React.useRef(fontSize);
  fontSizeRef.current = fontSize;
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const termRef = React.useRef<Terminal | null>(null);
  const fitRef = React.useRef<FitAddon | null>(null);
  const wsRef = React.useRef<WebSocket | null>(null);
  const [status, setStatus] = React.useState<Status>("closed");
  const [error, setError] = React.useState<string | null>(null);
  const [banner, setBanner] = React.useState<string | null>(null);

  const disconnect = React.useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    termRef.current?.dispose();
    termRef.current = null;
    fitRef.current = null;
    setStatus("closed");
  }, []);

  const connect = React.useCallback(() => {
    if (!serverId || !containerRef.current) return;
    disconnect();
    setError(null);
    setBanner(null);
    setStatus("connecting");

    const host = containerRef.current;
    const term = new Terminal({
      cursorBlink: true,
      fontSize: fontSizeRef.current,
      fontFamily:
        'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
      theme: {
        background: "#0f1014",
        foreground: "#e8eaed",
        cursor: "#c9b974",
        selectionBackground: "#3a3d45",
      },
      allowProposedApi: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host);
    try {
      fit.fit();
    } catch {
      /* ignore */
    }
    termRef.current = term;
    fitRef.current = fit;

    const cols = term.cols || 120;
    const rows = term.rows || 32;
    const ws = new WebSocket(infraSshWsUrl(serverId, cols, rows));
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connecting");
      term.writeln("\x1b[90mConnecting…\x1b[0m");
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(String(ev.data)) as {
          t: string;
          d?: string;
          m?: string;
          host?: string;
        };
        if (msg.t === "o" && msg.d) {
          term.write(msg.d);
        } else if (msg.t === "ready") {
          setStatus("ready");
          setBanner(msg.host || null);
          term.clear();
        } else if (msg.t === "e") {
          setStatus("error");
          setError(msg.m || "SSH error");
          term.writeln(`\r\n\x1b[31m${msg.m || "SSH error"}\x1b[0m`);
        }
      } catch {
        term.write(String(ev.data));
      }
    };

    ws.onerror = () => {
      setStatus("error");
      setError("WebSocket error");
    };

    ws.onclose = () => {
      setStatus((s) => (s === "error" ? s : "closed"));
      term.writeln("\r\n\x1b[90m[session closed]\x1b[0m");
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ t: "i", d: data }));
      }
    });

    const onResize = () => {
      try {
        fit.fit();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ t: "r", c: term.cols, r: term.rows }));
        }
      } catch {
        /* ignore */
      }
    };
    window.addEventListener("resize", onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(host);

    return () => {
      window.removeEventListener("resize", onResize);
      ro.disconnect();
    };
  }, [serverId, disconnect]);

  React.useEffect(() => {
    if (!serverId) {
      disconnect();
      return;
    }
    const cleanup = connect();
    return () => {
      cleanup?.();
      disconnect();
    };
  }, [serverId, connect, disconnect]);

  React.useEffect(() => {
    if (termRef.current) {
      termRef.current.options.fontSize = fontSize;
      try {
        fitRef.current?.fit();
      } catch {
        /* ignore */
      }
    }
  }, [fontSize]);

  return {
    containerRef,
    status,
    error,
    banner,
    reconnect: connect,
    disconnect,
  };
}
