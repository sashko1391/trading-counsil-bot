import { useState, useEffect, useRef, useCallback } from "react";
import { useBotData, useHistoryData } from "./useApi.js";
import HistoryPanel from "./HistoryPanel.jsx";

// ─── THEMES ───────────────────────────────────────────────────────────────────
const THEMES = {
  matrix:  { name: "МАТРИЦЯ",   accent: "#00ff41", dim: "#00aa2a", dark: "#005c1a", darker: "#001a06", bg: "#000800", panel: "rgba(0,8,0,0.85)" },
  amber:   { name: "БУРШТИН",   accent: "#ffb000", dim: "#cc8800", dark: "#664600", darker: "#2a1a00", bg: "#080400", panel: "rgba(8,4,0,0.85)" },
  cyber:   { name: "КІБЕРСИНІЙ",accent: "#00e5ff", dim: "#00aacc", dark: "#005966", darker: "#001a22", bg: "#000608", panel: "rgba(0,6,8,0.85)" },
};

const AGENT_META = {
  grok:       { role: "Настрій ринку",    icon: "𝕏" },
  perplexity: { role: "Перевірка фактів",  icon: "⊕" },
  gemini:     { role: "Макроаналіз",       icon: "◈" },
  claude:     { role: "Ризик-менеджер",    icon: "◆" },
};

const MATRIX_CHARS = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ0123456789АБВГДЕЄЖЗИ";

function generatePriceData(start, vol, n = 60) {
  const d = []; let p = start;
  for (let i = n - 1; i >= 0; i--) { p += (Math.random() - 0.47) * vol; d.push({ t: i, p: +p.toFixed(2) }); }
  return d;
}

// ─── MATRIX RAIN ────────────────────────────────────────────────────────────
function MatrixRain({ opacity = 0.18 }) {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize(); window.addEventListener("resize", resize);
    const fs = 13, cols = Math.floor(c.width / fs);
    const drops = Array(cols).fill(1);
    let rafId = 0;
    let lastTime = 0;
    const draw = (ts) => {
      rafId = requestAnimationFrame(draw);
      if (ts - lastTime < 40) return; // throttle to ~25fps
      lastTime = ts;
      ctx.fillStyle = "rgba(0,0,0,0.05)"; ctx.fillRect(0, 0, c.width, c.height);
      for (let i = 0; i < drops.length; i++) {
        const ch = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
        ctx.fillStyle = Math.random() > 0.95 ? "#fff" : `rgba(0,${180+Math.floor(Math.random()*75)},${Math.floor(Math.random()*40)},${0.6+Math.random()*0.4})`;
        ctx.font = `${fs}px monospace`; ctx.fillText(ch, i * fs, drops[i] * fs);
        if (drops[i] * fs > c.height && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
      }
    };
    rafId = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(rafId); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} style={{ position: "fixed", top: 0, left: 0, zIndex: 0, opacity, pointerEvents: "none", transition: "opacity 0.5s" }} />;
}

// ─── MINI CHART ─────────────────────────────────────────────────────────────
function MiniChart({ data, accent }) {
  const [tooltip, setTooltip] = useState(null);
  const svgRef = useRef(null);
  const W = 300, H = 65;
  const prices = data.map(d => d.p);
  const min = Math.min(...prices), max = Math.max(...prices);
  const range = max - min || 1;
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((d.p - min) / range) * (H - 6) - 3;
    return [x, y];
  });
  const polyPts = pts.map(p => p.join(",")).join(" ");
  const areaPath = `M 0,${H} L ${pts.map(p => p.join(",")).join(" L ")} L ${W},${H} Z`;
  const isUp = data[data.length - 1].p >= data[0].p;
  const lineColor = isUp ? "#00ff41" : "#ff4444";
  const gradId = `g${accent.replace(/[^a-z0-9]/gi, "")}`;

  const handleMove = (e) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const idx = Math.round(relX * (data.length - 1));
    const clamped = Math.max(0, Math.min(data.length - 1, idx));
    setTooltip({ idx: clamped, x: pts[clamped][0], y: pts[clamped][1], p: data[clamped].p });
  };

  return (
    <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block", cursor: "crosshair" }}
      onMouseMove={handleMove} onMouseLeave={() => setTooltip(null)}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.2" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradId})`} />
      <polyline points={polyPts} fill="none" stroke={lineColor} strokeWidth="1.4" strokeLinejoin="round" />
      {tooltip && (
        <>
          <line x1={tooltip.x} y1={0} x2={tooltip.x} y2={H} stroke={lineColor} strokeWidth="0.5" strokeDasharray="2,2" opacity="0.6" />
          <circle cx={tooltip.x} cy={tooltip.y} r="3" fill={lineColor} style={{ filter: `drop-shadow(0 0 4px ${lineColor})` }} />
          <rect x={Math.min(tooltip.x + 4, W - 60)} y={tooltip.y - 18} width="56" height="16" fill="#000800" stroke={lineColor} strokeWidth="0.5" rx="1" />
          <text x={Math.min(tooltip.x + 7, W - 57)} y={tooltip.y - 6} fill={lineColor} fontSize="9" fontFamily="monospace">${tooltip.p.toFixed(2)}</text>
        </>
      )}
      {(() => {
        const [lx, ly] = pts[pts.length - 1];
        return <circle cx={lx} cy={ly} r="2.5" fill={lineColor} style={{ filter: `drop-shadow(0 0 5px ${lineColor})` }} />;
      })()}
    </svg>
  );
}

// ─── CONFIDENCE GAUGE ───────────────────────────────────────────────────────
function ConfidenceGauge({ value, color }) {
  const R = 28, C = 2 * Math.PI * R;
  const filled = (value / 100) * C;
  return (
    <svg width={70} height={70} viewBox="0 0 70 70">
      <circle cx={35} cy={35} r={R} fill="none" stroke={`${color}22`} strokeWidth="4" />
      <circle cx={35} cy={35} r={R} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${filled} ${C}`} strokeLinecap="round"
        transform="rotate(-90 35 35)"
        style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: "stroke-dasharray 0.6s ease" }} />
      <text x={35} y={38} textAnchor="middle" fill={color} fontSize="13" fontFamily="monospace" fontWeight="700">{value}%</text>
    </svg>
  );
}

// ─── COMMAND PALETTE ────────────────────────────────────────────────────────
function CommandPalette({ open, onClose, theme, setTheme, focusMode, setFocusMode, rainOpacity, setRainOpacity }) {
  const [query, setQuery] = useState("");
  const T = THEMES[theme];
  const commands = [
    { key: "matrix",  label: "Тема: МАТРИЦЯ",      action: () => setTheme("matrix") },
    { key: "amber",   label: "Тема: БУРШТИН",       action: () => setTheme("amber") },
    { key: "cyber",   label: "Тема: КІБЕРСИНІЙ",    action: () => setTheme("cyber") },
    { key: "focus",   label: focusMode ? "Режим фокусу: ВИМКНУТИ" : "Режим фокусу: УВІМКНУТИ", action: () => setFocusMode(f => !f) },
    { key: "rain+",   label: "Матричний дощ: ЯСКРАВІШЕ", action: () => setRainOpacity(r => Math.min(0.5, r + 0.08)) },
    { key: "rain-",   label: "Матричний дощ: ТИХІШЕ", action: () => setRainOpacity(r => Math.max(0, r - 0.08)) },
    { key: "rain0",   label: "Матричний дощ: ВИМКНУТИ", action: () => setRainOpacity(0) },
  ];
  const filtered = commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()));

  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: 120, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={onClose}>
      <div style={{ background: T.panel, border: `1px solid ${T.accent}`, width: 420, maxHeight: 360, overflow: "hidden", boxShadow: `0 0 40px ${T.accent}33` }}
        onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderBottom: `1px solid ${T.dark}` }}>
          <span style={{ color: T.dim, fontSize: 11, fontFamily: "monospace" }}>⌘</span>
          <input value={query} onChange={e => setQuery(e.target.value)} autoFocus
            placeholder="введи команду..."
            style={{ flex: 1, background: "none", border: "none", color: T.accent, fontSize: 12, fontFamily: "monospace", outline: "none" }} />
          <span style={{ color: T.dark, fontSize: 10, fontFamily: "monospace" }}>ESC</span>
        </div>
        {filtered.map((c) => (
          <div key={c.key} onClick={() => { c.action(); onClose(); }}
            style={{ padding: "10px 14px", cursor: "pointer", fontSize: 11, fontFamily: "monospace", color: T.dim, borderBottom: `1px solid ${T.darker}`,
              transition: "background 0.1s" }}
            onMouseEnter={e => e.currentTarget.style.background = `${T.accent}11`}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
            <span style={{ color: T.dark, marginRight: 8 }}>&gt;</span>{c.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── AGENT CARD (wired to real data) ──────────────────────────────────────────
function AgentCard({ name, agentData, theme, visible, focusMode }) {
  const T = THEMES[theme];
  const [expanded, setExpanded] = useState(false);
  const meta = AGENT_META[name] || { role: name, icon: "?" };

  const statusLabel = agentData?.status || "ОЧІКУВАННЯ";
  const detail = agentData?.thesis || "Очікує на дані...";
  const confidence = agentData?.confidence ?? 0;
  const riskNotes = agentData?.risk_notes || "";

  const statusColors = { "BULLISH": T.accent, "BEARISH": "#ff4444", "NEUTRAL": "#ffaa00" };
  const statusUa = { "BULLISH": "БИЧАЧИЙ", "BEARISH": "ВЕДМЕЖИЙ", "NEUTRAL": "НЕЙТРАЛЬНО" };
  const sc = statusColors[statusLabel] || T.dim;

  return (
    <div onClick={() => setExpanded(e => !e)}
      style={{ background: T.panel, border: `1px solid ${expanded ? T.accent : T.dark}`, padding: "12px 14px", cursor: "pointer",
        opacity: visible ? (focusMode ? 0.4 : 1) : 0, transform: visible ? "translateX(0)" : "translateX(10px)", transition: "all 0.35s ease",
        boxShadow: expanded ? `0 0 12px ${T.accent}22` : "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14, color: T.accent, textShadow: `0 0 8px ${T.accent}` }}>{meta.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.accent, fontFamily: "monospace", textShadow: `0 0 6px ${T.accent}88` }}>
            {name.charAt(0).toUpperCase() + name.slice(1)}
          </div>
          <div style={{ fontSize: 9, color: T.dark, fontFamily: "monospace", letterSpacing: "0.06em" }}>{meta.role}</div>
        </div>
        <div style={{ fontSize: 9, fontWeight: 700, color: sc, fontFamily: "monospace", letterSpacing: "0.1em", textShadow: `0 0 6px ${sc}88` }}>
          {statusUa[statusLabel] || statusLabel}
        </div>
        <span style={{ fontSize: 9, color: T.dim, fontFamily: "monospace" }}>{Math.round(confidence * 100)}%</span>
        <span style={{ color: T.dark, fontSize: 10, marginLeft: 4 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      <div style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", marginTop: 6, borderLeft: `1px solid ${T.dark}`, paddingLeft: 8,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 260 }}>
        {detail.slice(0, 100)}
      </div>
      <div style={{ maxHeight: expanded ? 200 : 0, overflow: "hidden", transition: "max-height 0.3s ease" }}>
        <div style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", marginTop: 10, padding: "8px 10px",
          background: T.darker, borderLeft: `2px solid ${T.accent}`, lineHeight: 1.7 }}>
          <div>{detail}</div>
          {riskNotes && <div style={{ marginTop: 6, color: "#ffaa00" }}>⚠ {riskNotes}</div>}
        </div>
      </div>
    </div>
  );
}

// ─── SIGNAL ROW ──────────────────────────────────────────────────────────────
function SignalRow({ s, idx, theme, isNew }) {
  const T = THEMES[theme];
  const [flash, setFlash] = useState(isNew);
  useEffect(() => { if (isNew) { setFlash(true); setTimeout(() => setFlash(false), 700); } }, [isNew]);

  const actionUa = { "LONG": "КУПІВЛЯ", "SHORT": "ПРОДАЖ", "WAIT": "ОЧІКУВАННЯ", "CONFLICT": "КОНФЛІКТ" };
  const strengthUa = { "UNANIMOUS": "ОДНОСТАЙНО", "STRONG": "СИЛЬНО", "WEAK": "СЛАБКО", "NONE": "—" };
  const actionColor = { "LONG": T.accent, "SHORT": "#ff4444", "WAIT": T.dark, "CONFLICT": "#ffaa00" };

  const conf = Math.round((s.confidence || 0) * 100);
  const consensusLabel = strengthUa[s.consensus_strength] || s.consensus_strength || "—";
  const consensusStyle = s.consensus_strength === "UNANIMOUS"
    ? { bg: T.accent, color: "#000", weight: 900 }
    : s.consensus_strength === "NONE" || s.consensus === "CONFLICT"
      ? { bg: "transparent", color: "#ffaa00", weight: 700, border: "1px dashed #ffaa00" }
      : { bg: "transparent", color: T.dim };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "48px 1fr 100px 72px 50px", gap: 10,
      padding: "8px 0", borderBottom: `1px solid ${T.darker}`, alignItems: "center",
      opacity: Math.max(0.2, 1 - idx * 0.16),
      background: flash ? `${T.accent}18` : "transparent", transition: "background 0.5s ease" }}>
      <span style={{ fontSize: 10, color: T.dark, fontFamily: "monospace" }}>{s.time || "—"}</span>
      <div>
        <span style={{ fontSize: 10, fontWeight: 700, color: actionColor[s.action || s.consensus] || T.accent, fontFamily: "monospace" }}>
          {s.allowed === false ? "⛔ " : ""}{actionUa[s.action || s.consensus] || s.consensus}
        </span>
        <div style={{ fontSize: 9, color: T.dark, fontFamily: "monospace", marginTop: 2, lineHeight: 1.4,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 300 }}>
          {s.reason || "—"}
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "center" }}>
        <span style={{ fontSize: 8, fontFamily: "monospace", padding: "2px 6px", background: consensusStyle.bg,
          color: consensusStyle.color, fontWeight: consensusStyle.weight, border: consensusStyle.border }}>
          {consensusLabel}
        </span>
      </div>
      <span style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", textAlign: "right" }}>
        {s.price ? `$${Number(s.price).toFixed(2)}` : "—"}
      </span>
      <span style={{ fontSize: 10, fontFamily: "monospace", textAlign: "right",
        color: conf > 70 ? T.accent : conf > 40 ? "#ffaa00" : T.dark }}>
        {conf > 0 ? `${conf}%` : "—"}
      </span>
    </div>
  );
}

// ─── MAIN ────────────────────────────────────────────────────────────────────
export default function WarRoom() {
  const { forecast, agents, prices, riskScore, signals, events, status, wsConnected } = useBotData();

  const [activeTab, setActiveTab] = useState("dashboard"); // "dashboard" | "history"
  const historyData = useHistoryData("BZ=F");

  const [theme, setTheme] = useState("matrix");
  const [focusMode, setFocusMode] = useState(false);
  const [rainOpacity, setRainOpacity] = useState(0.18);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [riskCollapsed, setRiskCollapsed] = useState(false);
  const [agentsVisible, setAgentsVisible] = useState(false);
  const [glitch, setGlitch] = useState(false);
  const [time, setTime] = useState(new Date());

  // Price chart data (maintained locally, updated from API)
  const [brentData, setBrentData] = useState(() => generatePriceData(82.0, 0.4));
  const [gasoilData, setGasoilData] = useState(() => generatePriceData(1184.0, 5.0));
  const [brentFlash, setBrentFlash] = useState(false);
  const [gasoilFlash, setGasoilFlash] = useState(false);

  const T = THEMES[theme];

  // Extract prices from API
  const brentPrice = prices?.["BZ=F"]?.price || brentData[brentData.length - 1]?.p || 82.0;
  const gasoilPrice = prices?.["LGO"]?.price || gasoilData[gasoilData.length - 1]?.p || 1184.0;
  const brentChange = forecast?.instrument === "BZ=F" && forecast?.current_price
    ? ((brentPrice - forecast.current_price) / forecast.current_price * 100) : 0;
  const gasoilChange = 0;

  // Update chart data when prices change
  useEffect(() => {
    if (prices?.["BZ=F"]?.price) {
      setBrentData(d => [...d.slice(1), { t: 0, p: prices["BZ=F"].price }]);
      setBrentFlash(true); setTimeout(() => setBrentFlash(false), 220);
    }
  }, [prices?.["BZ=F"]?.price]);

  useEffect(() => {
    if (prices?.["LGO"]?.price) {
      setGasoilData(d => [...d.slice(1), { t: 0, p: prices["LGO"].price }]);
      setGasoilFlash(true); setTimeout(() => setGasoilFlash(false), 220);
    }
  }, [prices?.["LGO"]?.price]);

  // Clock + glitch
  useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => { setTimeout(() => setAgentsVisible(true), 400); }, []);
  useEffect(() => { const g = setInterval(() => { setGlitch(true); setTimeout(() => setGlitch(false), 120); }, 5000); return () => clearInterval(g); }, []);

  // Keyboard: Cmd+K
  useEffect(() => {
    const h = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setPaletteOpen(p => !p); } if (e.key === "Escape") setPaletteOpen(false); };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, []);

  // Forecast data
  const isBull = forecast?.direction === "BULLISH";
  const isBear = forecast?.direction === "BEARISH";
  const mainColor = isBull ? T.accent : isBear ? "#ff4444" : "#ffaa00";
  const confPct = Math.round((forecast?.confidence || 0) * 100);
  const drivers = forecast?.drivers || [];
  const volatility = Math.abs(brentChange);
  const isAlert = volatility > 2.5;

  // Risk score
  const rs = riskScore || {};
  const composite = rs.composite || (
    ((rs.geopolitical || 0) * 0.25 + (rs.supply || 0) * 0.25 + (rs.demand || 0) * 0.20 +
     (rs.financial || 0) * 0.10 + (rs.seasonal || 0) * 0.10 + (rs.technical || 0) * 0.10) || 0
  );
  const compositeDisplay = (composite * 10).toFixed(1);

  const riskItems = [
    { l: "Геополітика", v: rs.geopolitical || 0 },
    { l: "Пропозиція", v: rs.supply || 0 },
    { l: "Попит", v: rs.demand || 0 },
    { l: "Фінанси", v: rs.financial || 0 },
    { l: "Сезонність", v: rs.seasonal || 0 },
    { l: "Технічний", v: rs.technical || 0 },
  ];

  // Agent list
  const agentNames = ["grok", "perplexity", "gemini", "claude"];

  // Events
  const eventImpactMap = { "high": "КРИТИЧНО", "medium": "СЕРЕДНЬО", "low": "НИЗЬКО" };

  const secOpacity = focusMode ? 0.2 : 1;

  // Status indicator
  const statusLabel = wsConnected ? "WS" : "REST";
  const statusColor = status === "active" ? T.accent : status === "idle" ? "#ffaa00" : T.dark;

  // Ticker
  const tickerItems = [
    `BRENT $${brentPrice.toFixed(2)}`,
    `HO $${gasoilPrice.toFixed(0)}/т`,
    `РИЗИК ${compositeDisplay}/10`,
    `КОНСЕНСУС: ${forecast?.direction || "—"}`,
    `СТАТУС: ${status.toUpperCase()}`,
  ].join("  ·  ");

  return (
    <div style={{ background: T.bg, minHeight: "100vh", color: T.accent, fontFamily: "monospace", overflow: "hidden" }}>
      <MatrixRain opacity={rainOpacity} />

      {/* Scanlines */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1,
        backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.07) 3px, rgba(0,0,0,0.07) 4px)" }} />

      {isAlert && <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1,
        border: `2px solid ${T.accent}66`, boxShadow: `inset 0 0 60px ${T.accent}08` }} />}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
        theme={theme} setTheme={setTheme} focusMode={focusMode} setFocusMode={setFocusMode}
        rainOpacity={rainOpacity} setRainOpacity={setRainOpacity} />

      <div style={{ position: "relative", zIndex: 2, maxWidth: 1400, margin: "0 auto", padding: "0 14px" }}>

        {/* ── TOP BAR ── */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 0", borderBottom: `1px solid ${T.dark}`, position: "sticky", top: 0, zIndex: 20,
          background: T.bg, backdropFilter: "blur(8px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 900, letterSpacing: "0.2em", color: T.accent, textShadow: `0 0 12px ${T.accent}` }}>
              🛢 НАФТОВА_РАДА.EXE
            </span>
            <div style={{ width: 6, height: 6, background: statusColor, boxShadow: `0 0 10px ${statusColor}` }} />
            <span style={{ fontSize: 9, color: statusColor, letterSpacing: "0.2em" }}>
              [ {status === "active" ? "СИСТЕМА АКТИВНА" : status === "idle" ? "ОЧІКУВАННЯ" : "ПІДКЛЮЧЕННЯ..."} · {statusLabel} ]
            </span>
            <div style={{ display: "flex", gap: 2, marginLeft: 14 }}>
              {[
                { key: "dashboard", label: "ДАШБОРД" },
                { key: "history", label: "ІСТОРІЯ" },
              ].map(tab => (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  style={{
                    background: activeTab === tab.key ? `${T.accent}22` : "transparent",
                    border: `1px solid ${activeTab === tab.key ? T.accent : T.dark}`,
                    color: activeTab === tab.key ? T.accent : T.dark,
                    fontSize: 9, padding: "3px 10px", fontFamily: "monospace", cursor: "pointer",
                    letterSpacing: "0.12em", transition: "all 0.2s",
                    textShadow: activeTab === tab.key ? `0 0 6px ${T.accent}88` : "none",
                  }}>
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
            {[
              { label: "БРЕНТ BZ=F", price: brentPrice, change: brentChange, flash: brentFlash },
              { label: "ДИСТИЛЯТИ HO", price: gasoilPrice, change: gasoilChange, flash: gasoilFlash },
            ].map((item) => (
              <div key={item.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.15em" }}>{item.label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "monospace",
                  color: item.change >= 0 ? T.accent : "#ff4444",
                  textShadow: `0 0 ${item.flash ? "18px" : "8px"} ${item.change >= 0 ? T.accent : "#ff4444"}`,
                  transition: "text-shadow 0.25s ease" }}>
                  ${item.price.toFixed(2)}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <button onClick={() => setPaletteOpen(true)}
              style={{ background: "none", border: `1px solid ${T.dark}`, color: T.dim, fontSize: 9, padding: "3px 8px",
                fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.1em" }}>
              ⌘ КОМАНДИ
            </button>
            <div style={{ fontSize: 11, color: T.dark, letterSpacing: "0.1em" }}>{time.toLocaleTimeString("uk-UA")}</div>
          </div>
        </div>

        {/* ── TICKER ── */}
        <div style={{ overflow: "hidden", borderBottom: `1px solid ${T.darker}`, background: T.darker }}>
          <div style={{ display: "inline-block", whiteSpace: "nowrap", animation: "ticker 25s linear infinite",
            fontSize: 9, color: T.dim, padding: "5px 0", letterSpacing: "0.1em" }}>
            {tickerItems}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{tickerItems}
          </div>
        </div>
        <style>{`@keyframes ticker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }`}</style>

        {/* ── HISTORY TAB ── */}
        {activeTab === "history" && (
          <div style={{ paddingTop: 12 }}>
            <HistoryPanel
              theme={T}
              daily={historyData.daily}
              digests={historyData.digests}
              agentHistory={historyData.agentHistory}
              loading={historyData.loading}
              onRefresh={historyData.refetch}
            />
          </div>
        )}

        {/* ── MAIN GRID (DASHBOARD) ── */}
        {activeTab === "dashboard" && <div style={{ display: "grid", gridTemplateColumns: "1fr 295px", gap: 12, paddingTop: 12 }}>

          {/* ── LEFT ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

            {/* FORECAST — STICKY */}
            <div style={{ position: "sticky", top: 57, zIndex: 10,
              background: T.panel, border: `1px solid ${mainColor}`,
              padding: "18px 22px", boxShadow: `0 0 ${isAlert ? "50px" : "25px"} ${mainColor}18, inset 0 0 50px ${mainColor}04`,
              transition: "box-shadow 1.5s ease" }}>
              <div style={{ position: "absolute", top: 0, left: "8%", right: "8%", height: 1,
                background: `linear-gradient(90deg, transparent, ${mainColor}, transparent)` }} />

              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <div style={{ width: 7, height: 7, background: mainColor, boxShadow: `0 0 10px ${mainColor}` }} />
                <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.2em" }}>// ПРОГНОЗ РАДИ · НАСТУПНІ 12 ГОДИН</span>
                {isAlert && <span style={{ fontSize: 9, color: "#ffaa00", letterSpacing: "0.15em", marginLeft: "auto" }}>[ ВИСОКА ВОЛАТИЛЬНІСТЬ ]</span>}
              </div>

              <div style={{ display: "flex", alignItems: "flex-start", gap: 20 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 10, color: T.dark, letterSpacing: "0.2em", marginBottom: 8 }}>НАША_ДУМКА::</div>
                  <div style={{ fontSize: 30, fontWeight: 900, fontFamily: "monospace", lineHeight: 1,
                    color: mainColor, textShadow: `0 0 20px ${mainColor}, 0 0 40px ${mainColor}66`,
                    transform: glitch ? "translateX(2px)" : "translateX(0)", transition: "transform 0.05s",
                    letterSpacing: "0.04em" }}>
                    {forecast ? (isBull ? "▲ ЦІНА ЗРОСТАТИМЕ" : isBear ? "▼ ЦІНА ПАДАТИМЕ" : "— НЕВИЗНАЧЕНО") : "⏳ ОЧІКУВАННЯ ДАНИХ..."}
                  </div>
                  {forecast && (
                    <div style={{ fontSize: 12, color: T.dim, marginTop: 10, fontFamily: "monospace",
                      lineHeight: 1.7, maxWidth: 440, borderLeft: `2px solid ${T.dark}`, paddingLeft: 12 }}>
                      Ціль: ${forecast.target_price?.toFixed(2)} · Стоп: ${forecast.stop_loss_price?.toFixed(2) || "—"}
                      <br/>{drivers.join(". ")}
                    </div>
                  )}
                </div>

                <div style={{ flexShrink: 0, borderLeft: `1px solid ${T.dark}`, paddingLeft: 18, textAlign: "center" }}>
                  <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.15em", marginBottom: 4 }}>ВПЕВНЕНІСТЬ</div>
                  <ConfidenceGauge value={confPct} color={mainColor} />
                </div>
              </div>

              {drivers.length > 0 && (
                <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
                  {drivers.map((f, i) => (
                    <span key={i} style={{ fontSize: 9, color: T.dim, background: `${T.accent}08`,
                      border: `1px solid ${T.dark}`, padding: "3px 8px", fontFamily: "monospace", letterSpacing: "0.1em",
                      maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      [{f.slice(0, 40)}]
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* CHARTS */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, opacity: focusMode ? 0.7 : 1, transition: "opacity 0.4s" }}>
              {[
                { title: "Нафта Brent", ticker: "BZ=F · 1 ГОД.", price: brentPrice, change: brentChange, data: brentData },
                { title: "Дистиляти (HO proxy)", ticker: "HO=F · $/т", price: gasoilPrice, change: gasoilChange, data: gasoilData },
              ].map((c) => (
                <div key={c.title} style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <div>
                      <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.12em" }}>{c.ticker}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: T.dim, fontFamily: "monospace" }}>{c.title}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 17, fontWeight: 700, color: c.change >= 0 ? T.accent : "#ff4444",
                        textShadow: `0 0 8px ${c.change >= 0 ? T.accent : "#ff4444"}`, fontFamily: "monospace" }}>
                        ${c.price.toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <MiniChart data={c.data} accent={T.accent} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9, color: T.dark, fontFamily: "monospace" }}>
                    <span>МІН ${Math.min(...c.data.map(d => d.p)).toFixed(2)}</span>
                    <span>МАКС ${Math.max(...c.data.map(d => d.p)).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* RISK */}
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px", opacity: focusMode ? 0.2 : 1, transition: "opacity 0.4s" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: riskCollapsed ? 0 : 12, cursor: "pointer" }}
                onClick={() => setRiskCollapsed(r => !r)}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                  <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>РИЗИК-КОНТРОЛЬ</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span style={{ fontSize: 22, fontWeight: 900, color: composite > 0.6 ? "#ff4444" : "#ffaa00", fontFamily: "monospace" }}>
                    {compositeDisplay}<span style={{ fontSize: 11, color: T.dark }}>/10</span>
                  </span>
                  <span style={{ color: T.dark, fontSize: 11 }}>{riskCollapsed ? "[+]" : "[−]"}</span>
                </div>
              </div>
              <div style={{ maxHeight: riskCollapsed ? 0 : 200, overflow: "hidden", transition: "max-height 0.35s ease" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px 18px" }}>
                  {riskItems.map(r => {
                    const val = Math.round(r.v * 10);
                    return (
                      <div key={r.l}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                          <span style={{ fontSize: 8, color: T.dark, letterSpacing: "0.08em" }}>{r.l.toUpperCase()}</span>
                          <span style={{ fontSize: 8, color: val >= 7 ? "#ff4444" : val >= 5 ? "#ffaa00" : T.accent, fontFamily: "monospace" }}>{val}/10</span>
                        </div>
                        <div style={{ height: 2, background: T.darker }}>
                          <div style={{ height: 2, width: `${val * 10}%`, transition: "width 0.4s",
                            background: val >= 7 ? "#ff4444" : val >= 5 ? "#ffaa00" : T.accent,
                            boxShadow: `0 0 4px ${val >= 7 ? "#ff4444" : val >= 5 ? "#ffaa00" : T.accent}` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* SIGNAL HISTORY */}
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px", opacity: focusMode ? 0.2 : 1, transition: "opacity 0.4s" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                  <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ІСТОРІЯ ПРОГНОЗІВ</span>
                </div>
                <span style={{ fontSize: 9, color: T.dim, fontFamily: "monospace" }}>СИГНАЛІВ: {signals.length}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "48px 1fr 100px 72px 50px", gap: 10, marginBottom: 6 }}>
                {["ЧАС", "СИГНАЛ", "КОНСЕНСУС", "ЦІНА", "ВПЕВН."].map(h => (
                  <span key={h} style={{ fontSize: 8, color: T.darker, letterSpacing: "0.12em" }}>{h}</span>
                ))}
              </div>
              {signals.length === 0 && (
                <div style={{ textAlign: "center", padding: 20, fontSize: 10, color: T.dark }}>
                  Очікування першого сигналу...
                </div>
              )}
              {signals.slice(0, 10).map((s, i) => <SignalRow key={`${s.time}-${i}`} s={s} idx={i} theme={theme} isNew={i === 0} />)}
            </div>
          </div>

          {/* ── RIGHT ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.2em", paddingTop: 2 }}>// СТАТУС AI РАДИ</div>
            {agentNames.map(name => (
              <AgentCard key={name} name={name} agentData={agents[name]} theme={theme} visible={agentsVisible} focusMode={focusMode} />
            ))}

            {/* EVENTS */}
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px", opacity: secOpacity, transition: "opacity 0.4s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ЗАПЛАНОВАНІ ПОДІЇ</span>
              </div>
              {events.length === 0 && (
                <div style={{ fontSize: 9, color: T.dark, padding: "8px 0" }}>Немає подій в найближчі 48г</div>
              )}
              {events.slice(0, 5).map((e, i) => (
                <div key={i} style={{ padding: "7px 0", borderBottom: `1px solid ${T.darker}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 10, color: T.dim, fontFamily: "monospace" }}>{e.name}</span>
                    <span style={{ fontSize: 8, color: e.impact_level === "high" ? "#ff4444" : "#ffaa00", letterSpacing: "0.1em" }}>
                      {eventImpactMap[e.impact_level] || e.impact_level}
                    </span>
                  </div>
                  <div style={{ fontSize: 9, color: T.dark, marginTop: 2 }}>{e.datetime || ""}</div>
                </div>
              ))}
            </div>

            {/* CONNECTION STATUS */}
            <div style={{ background: T.panel, border: `1px solid ${wsConnected ? T.accent + "44" : "#ff444444"}`, padding: "10px 14px",
              display: "flex", alignItems: "center", gap: 10, opacity: secOpacity, transition: "opacity 0.4s" }}>
              <span>{wsConnected ? "🟢" : "🔴"}</span>
              <div>
                <div style={{ fontSize: 10, color: wsConnected ? T.accent : "#ff4444", fontFamily: "monospace", letterSpacing: "0.1em" }}>
                  {wsConnected ? "LIVE · WEBSOCKET" : "POLLING · REST API"}
                </div>
                <div style={{ fontSize: 9, color: T.dark, marginTop: 2 }}>
                  Бекенд: localhost:8000
                </div>
              </div>
            </div>

            <div style={{ fontSize: 8, color: T.dark, textAlign: "center", letterSpacing: "0.15em", padding: "4px 0" }}>
              ТЕМА: {THEMES[theme].name} · ⌘K — КОМАНДИ
            </div>
          </div>
        </div>}
      </div>

      <div aria-live="assertive" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", opacity: 0 }}>
        {`Прогноз: ${forecast?.direction || "очікування"}, впевненість ${confPct}%`}
      </div>
    </div>
  );
}
