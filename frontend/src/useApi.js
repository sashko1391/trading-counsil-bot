/**
 * React hooks for War Room ↔ FastAPI communication.
 * REST polling + WebSocket for real-time updates.
 */

import { useState, useEffect, useRef, useCallback } from "react";

// In dev: "" (Vite proxy handles /api → localhost:8000)
// In prod: set VITE_API_URL to the Railway backend URL
const API_BASE = import.meta.env.VITE_API_URL || "";

// ── REST fetcher ─────────────────────────────────────────────────────────────

async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── WebSocket hook ───────────────────────────────────────────────────────────

export function useWebSocket(onMessage) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    let url;
    if (API_BASE) {
      // Production: derive WS URL from API_BASE (https://foo.railway.app → wss://foo.railway.app/ws)
      url = API_BASE.replace(/^http/, "ws") + "/ws";
    } else {
      // Dev: same origin via Vite proxy
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      url = `${proto}//${window.location.host}/ws`;
    }
    const ws = new WebSocket(url);

    ws.onopen = () => console.log("[WS] connected");

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        onMessage(data);
      } catch (e) {
        console.warn("[WS] parse error", e);
      }
    };

    ws.onclose = () => {
      console.log("[WS] disconnected, reconnecting in 3s...");
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => console.warn("[WS] error", err);

    wsRef.current = ws;
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return wsRef;
}

// ── REST polling hook ────────────────────────────────────────────────────────

export function usePolling(path, intervalMs = 10000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;

    const poll = async () => {
      try {
        const json = await fetchJson(path);
        if (active) { setData(json); setError(null); }
      } catch (e) {
        if (active) setError(e.message);
      }
    };

    poll();
    const id = setInterval(poll, intervalMs);
    return () => { active = false; clearInterval(id); };
  }, [path, intervalMs]);

  return { data, error };
}

// ── One-shot fetch hook ─────────────────────────────────────────────────────

export function useFetch(path) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      const json = await fetchJson(path);
      setData(json);
    } catch (e) {
      console.warn(`Fetch ${path} failed:`, e);
    }
    setLoading(false);
  }, [path]);

  useEffect(() => { refetch(); }, [refetch]);

  return { data, loading, refetch };
}

// ── History data hook ───────────────────────────────────────────────────────

export function useHistoryData(instrument = "BZ=F") {
  const { data: digests, loading: digestsLoading, refetch: refetchDigests } =
    useFetch(`/api/history/digests?instrument=${instrument}&limit=24`);
  const { data: daily, loading: dailyLoading, refetch: refetchDaily } =
    useFetch(`/api/history/daily?instrument=${instrument}&limit=30`);
  const { data: agentHistory, loading: agentsLoading, refetch: refetchAgents } =
    useFetch(`/api/history/agents/all?instrument=${instrument}&limit=10`);

  const refetchAll = useCallback(() => {
    refetchDigests(); refetchDaily(); refetchAgents();
  }, [refetchDigests, refetchDaily, refetchAgents]);

  return {
    digests: Array.isArray(digests) ? digests : [],
    daily: Array.isArray(daily) ? daily : [],
    agentHistory: agentHistory && !agentHistory.error ? agentHistory : {},
    loading: digestsLoading || dailyLoading || agentsLoading,
    refetch: refetchAll,
  };
}

// ── Composite hook: merges WS + REST fallback ────────────────────────────────

export function useBotData() {
  const [forecast, setForecast] = useState(null);
  const [agents, setAgents] = useState({});
  const [prices, setPrices] = useState({});
  const [riskScore, setRiskScore] = useState(null);
  const [signals, setSignals] = useState([]);
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("connecting");
  const [wsConnected, setWsConnected] = useState(false);

  // WebSocket handler
  const handleWs = useCallback((msg) => {
    setWsConnected(true);

    if (msg.type === "init" || msg.type === "update") {
      if (msg.prices) setPrices(msg.prices);
      if (msg.forecast) setForecast(msg.forecast);
      if (msg.risk_score) setRiskScore(msg.risk_score);
      if (msg.agents) setAgents(msg.agents);
      if (msg.status) setStatus(msg.status);
    }

    if (msg.type === "init") {
      if (msg.signals) setSignals(msg.signals);
      if (msg.events) setEvents(msg.events);
    }

    if (msg.type === "update" && msg.latest_signal) {
      setSignals((prev) => [msg.latest_signal, ...prev].slice(0, 50));
    }
  }, []);

  useWebSocket(handleWs);

  // REST fallback polling (slower, for when WS is down)
  const { data: restForecast } = usePolling("/api/forecast", 15000);
  const { data: restAgents } = usePolling("/api/agents", 15000);
  const { data: restPrices } = usePolling("/api/prices", 5000);
  const { data: restRisk } = usePolling("/api/risk", 15000);
  const { data: restSignals } = usePolling("/api/signals?limit=20", 15000);
  const { data: restEvents } = usePolling("/api/events", 60000);
  const { data: restStatus } = usePolling("/api/status", 10000);

  // Merge: WS takes priority, REST fills gaps
  useEffect(() => {
    if (!wsConnected) {
      if (restForecast && !restForecast.message) setForecast(restForecast);
      if (restAgents && !restAgents.message) setAgents(restAgents);
      if (restPrices && !restPrices.message) setPrices(restPrices);
      if (restRisk?.risk_score) setRiskScore(restRisk.risk_score);
      if (Array.isArray(restSignals)) setSignals(restSignals);
      if (Array.isArray(restEvents)) setEvents(restEvents);
      if (restStatus?.status) setStatus(restStatus.status);
    }
  }, [wsConnected, restForecast, restAgents, restPrices, restRisk, restSignals, restEvents, restStatus]);

  return { forecast, agents, prices, riskScore, signals, events, status, wsConnected };
}
