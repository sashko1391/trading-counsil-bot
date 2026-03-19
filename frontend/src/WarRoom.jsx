import { useState, useEffect, useRef } from "react";
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

function generatePriceData(start, vol, n = 60) {
  const d = []; let p = start;
  for (let i = n - 1; i >= 0; i--) { p += (Math.random() - 0.47) * vol; d.push({ t: i, p: +p.toFixed(2) }); }
  return d;
}

// ─── useIsMobile ─────────────────────────────────────────────────────────────
function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < breakpoint);
  useEffect(() => {
    const h = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, [breakpoint]);
  return isMobile;
}

// ─── MATRIX RAIN ────────────────────────────────────────────────────────────
const MATRIX_CHARS = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ0123456789";

function MatrixRain({ opacity = 0.18, disabled = false }) {
  const ref = useRef(null);
  useEffect(() => {
    if (disabled) return;
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize(); window.addEventListener("resize", resize);
    const fs = 13, cols = Math.floor(c.width / fs);
    const drops = Array(cols).fill(1);
    let rafId = 0, lastTime = 0;
    const draw = (ts) => {
      rafId = requestAnimationFrame(draw);
      if (ts - lastTime < 40) return;
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
  }, [disabled]);
  if (disabled) return null;
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

  const handleInteract = (e) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const relX = (clientX - rect.left) / rect.width;
    const idx = Math.round(relX * (data.length - 1));
    const clamped = Math.max(0, Math.min(data.length - 1, idx));
    setTooltip({ idx: clamped, x: pts[clamped][0], y: pts[clamped][1], p: data[clamped].p });
  };

  return (
    <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block", cursor: "crosshair", touchAction: "none" }}
      onMouseMove={handleInteract} onTouchMove={handleInteract}
      onMouseLeave={() => setTooltip(null)} onTouchEnd={() => setTooltip(null)}>
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
function ConfidenceGauge({ value, color, size = 70 }) {
  const R = size * 0.4, C = 2 * Math.PI * R;
  const filled = (value / 100) * C;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={R} fill="none" stroke={`${color}22`} strokeWidth="4" />
      <circle cx={size/2} cy={size/2} r={R} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${filled} ${C}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: "stroke-dasharray 0.6s ease" }} />
      <text x={size/2} y={size/2+4} textAnchor="middle" fill={color} fontSize={size*0.19} fontFamily="monospace" fontWeight="700">{value}%</text>
    </svg>
  );
}

// ─── AGENT CARD ─────────────────────────────────────────────────────────────
function AgentCard({ name, agentData, theme, visible, isMobile }) {
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
      style={{ background: T.panel, border: `1px solid ${expanded ? T.accent : T.dark}`,
        padding: isMobile ? "10px 12px" : "12px 14px", cursor: "pointer",
        opacity: visible ? 1 : 0, transform: visible ? "translateX(0)" : "translateX(10px)", transition: "all 0.35s ease",
        boxShadow: expanded ? `0 0 12px ${T.accent}22` : "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14, color: T.accent, textShadow: `0 0 8px ${T.accent}` }}>{meta.icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.accent, fontFamily: "monospace" }}>
            {name.charAt(0).toUpperCase() + name.slice(1)}
          </div>
          <div style={{ fontSize: 9, color: T.dark, fontFamily: "monospace" }}>{meta.role}</div>
        </div>
        <div style={{ fontSize: 9, fontWeight: 700, color: sc, fontFamily: "monospace", letterSpacing: "0.08em", textShadow: `0 0 6px ${sc}88` }}>
          {statusUa[statusLabel] || statusLabel}
        </div>
        <span style={{ fontSize: 9, color: T.dim, fontFamily: "monospace" }}>{Math.round(confidence * 100)}%</span>
        <span style={{ color: T.dark, fontSize: 10 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {!expanded && (
        <div style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", marginTop: 5,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {detail.slice(0, isMobile ? 60 : 100)}
        </div>
      )}
      <div style={{ maxHeight: expanded ? 300 : 0, overflow: "hidden", transition: "max-height 0.3s ease" }}>
        <div style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", marginTop: 10, padding: "8px 10px",
          background: T.darker, borderLeft: `2px solid ${T.accent}`, lineHeight: 1.7, wordBreak: "break-word" }}>
          <div>{detail}</div>
          {riskNotes && <div style={{ marginTop: 6, color: "#ffaa00" }}>⚠ {riskNotes}</div>}
        </div>
      </div>
    </div>
  );
}

// ─── SIGNAL ROW (mobile-aware) ──────────────────────────────────────────────
function SignalRow({ s, idx, theme, isNew, isMobile }) {
  const T = THEMES[theme];
  const [flash, setFlash] = useState(isNew);
  useEffect(() => { if (isNew) { setFlash(true); setTimeout(() => setFlash(false), 700); } }, [isNew]);

  const actionUa = { "LONG": "КУПІВЛЯ", "SHORT": "ПРОДАЖ", "WAIT": "ОЧІКУВАННЯ", "CONFLICT": "КОНФЛІКТ" };
  const actionColor = { "LONG": T.accent, "SHORT": "#ff4444", "WAIT": T.dark, "CONFLICT": "#ffaa00" };
  const conf = Math.round((s.confidence || 0) * 100);

  if (isMobile) {
    return (
      <div style={{ padding: "8px 0", borderBottom: `1px solid ${T.darker}`,
        opacity: Math.max(0.3, 1 - idx * 0.12),
        background: flash ? `${T.accent}18` : "transparent", transition: "background 0.5s ease" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 10, color: T.dark, fontFamily: "monospace" }}>{s.time || "—"}</span>
            <span style={{ fontSize: 10, fontWeight: 700, color: actionColor[s.action || s.consensus] || T.accent, fontFamily: "monospace" }}>
              {s.allowed === false ? "⛔ " : ""}{actionUa[s.action || s.consensus] || s.consensus}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 10, color: T.dim, fontFamily: "monospace" }}>
              {s.price ? `$${Number(s.price).toFixed(0)}` : ""}
            </span>
            <span style={{ fontSize: 10, fontFamily: "monospace",
              color: conf > 70 ? T.accent : conf > 40 ? "#ffaa00" : T.dark }}>
              {conf > 0 ? `${conf}%` : ""}
            </span>
          </div>
        </div>
      </div>
    );
  }

  const strengthUa = { "UNANIMOUS": "ОДНОСТАЙНО", "STRONG": "СИЛЬНО", "WEAK": "СЛАБКО", "NONE": "—" };
  const consensusLabel = strengthUa[s.consensus_strength] || s.consensus_strength || "—";

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
        <div style={{ fontSize: 9, color: T.dark, fontFamily: "monospace", marginTop: 2,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 300 }}>
          {s.reason || "—"}
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "center" }}>
        <span style={{ fontSize: 8, fontFamily: "monospace", padding: "2px 6px",
          color: T.dim }}>{consensusLabel}</span>
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

// ─── INSTRUMENT TABS ────────────────────────────────────────────────────────
const INSTRUMENTS = [
  { key: "brent", label: "BRENT", sublabel: "BZ=F", active: true },
  { key: "diesel", label: "ДИЗЕЛЬ УКР", sublabel: "ОПТ", active: false },
];

// ─── MAIN ────────────────────────────────────────────────────────────────────
export default function WarRoom() {
  const { forecast, agents, prices, riskScore, signals, events, status, wsConnected } = useBotData();
  const isMobile = useIsMobile();

  const [activeTab, setActiveTab] = useState("dashboard");
  const [instrument, setInstrument] = useState("brent");
  const historyData = useHistoryData("BZ=F");

  const [theme, setTheme] = useState("matrix");
  const [riskCollapsed, setRiskCollapsed] = useState(isMobile);
  const [agentsVisible, setAgentsVisible] = useState(false);
  const [time, setTime] = useState(new Date());

  const [brentData, setBrentData] = useState(() => generatePriceData(82.0, 0.4));
  const [brentFlash, setBrentFlash] = useState(false);

  const T = THEMES[theme];

  const brentPrice = prices?.["BZ=F"]?.price || brentData[brentData.length - 1]?.p || 82.0;
  const brentChange = forecast?.instrument === "BZ=F" && forecast?.current_price
    ? ((brentPrice - forecast.current_price) / forecast.current_price * 100) : 0;

  useEffect(() => {
    if (prices?.["BZ=F"]?.price) {
      setBrentData(d => [...d.slice(1), { t: 0, p: prices["BZ=F"].price }]);
      setBrentFlash(true); setTimeout(() => setBrentFlash(false), 220);
    }
  }, [prices?.["BZ=F"]?.price]);

  useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => { setTimeout(() => setAgentsVisible(true), 400); }, []);

  // Forecast data
  const isBull = forecast?.direction === "BULLISH";
  const isBear = forecast?.direction === "BEARISH";
  const mainColor = isBull ? T.accent : isBear ? "#ff4444" : "#ffaa00";
  const confPct = Math.round((forecast?.confidence || 0) * 100);
  const drivers = forecast?.drivers || [];

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

  const agentNames = ["grok", "perplexity", "gemini", "claude"];
  const eventImpactMap = { "high": "КРИТИЧНО", "medium": "СЕРЕДНЬО", "low": "НИЗЬКО" };
  const statusColor = status === "active" ? T.accent : status === "idle" ? "#ffaa00" : T.dark;

  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ background: T.bg, minHeight: "100vh", color: T.accent, fontFamily: "monospace", overflow: "hidden" }}>
      <MatrixRain opacity={isMobile ? 0.08 : 0.18} disabled={false} />

      {/* Scanlines (lighter on mobile) */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1,
        backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px)" }} />

      <div style={{ position: "relative", zIndex: 2, maxWidth: 1400, margin: "0 auto", padding: isMobile ? "0 8px" : "0 14px" }}>

        {/* ── TOP BAR ── */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: isMobile ? "8px 0" : "12px 0", borderBottom: `1px solid ${T.dark}`,
          position: "sticky", top: 0, zIndex: 20, background: T.bg, backdropFilter: "blur(8px)",
          gap: 8, flexWrap: isMobile ? "wrap" : "nowrap" }}>

          {/* Left: logo + status */}
          <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 14, minWidth: 0 }}>
            <span style={{ fontSize: isMobile ? 11 : 13, fontWeight: 900, letterSpacing: "0.15em", color: T.accent,
              textShadow: `0 0 12px ${T.accent}`, whiteSpace: "nowrap" }}>
              🛢 РАДА
            </span>
            <div style={{ width: 6, height: 6, background: statusColor, boxShadow: `0 0 10px ${statusColor}`, flexShrink: 0 }} />
            {!isMobile && (
              <span style={{ fontSize: 9, color: statusColor, letterSpacing: "0.15em" }}>
                [ {status === "active" ? "АКТИВНА" : status === "idle" ? "ОЧІКУВАННЯ" : "ПІДКЛЮЧЕННЯ..."} ]
              </span>
            )}
          </div>

          {/* Center: price */}
          <div style={{ textAlign: "center", flexShrink: 0 }}>
            <div style={{ fontSize: isMobile ? 18 : 20, fontWeight: 700, fontFamily: "monospace",
              color: brentChange >= 0 ? T.accent : "#ff4444",
              textShadow: `0 0 ${brentFlash ? "18px" : "8px"} ${brentChange >= 0 ? T.accent : "#ff4444"}`,
              transition: "text-shadow 0.25s ease", lineHeight: 1 }}>
              ${brentPrice.toFixed(2)}
            </div>
            <div style={{ fontSize: 8, color: T.dark, letterSpacing: "0.1em", marginTop: 2 }}>BRENT</div>
          </div>

          {/* Right: time */}
          <div style={{ fontSize: isMobile ? 10 : 11, color: T.dark, letterSpacing: "0.08em", textAlign: "right", whiteSpace: "nowrap" }}>
            {time.toLocaleTimeString("uk-UA")}
          </div>
        </div>

        {/* ── INSTRUMENT TABS ── */}
        <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${T.darker}`, overflow: "auto" }}>
          {INSTRUMENTS.map(inst => (
            <button key={inst.key} onClick={() => inst.active && setInstrument(inst.key)}
              style={{
                flex: 1, padding: isMobile ? "8px 4px" : "10px 16px",
                background: instrument === inst.key ? `${T.accent}15` : "transparent",
                borderBottom: instrument === inst.key ? `2px solid ${T.accent}` : "2px solid transparent",
                border: "none", borderLeft: "none", borderRight: "none",
                color: !inst.active ? `${T.dark}88` : instrument === inst.key ? T.accent : T.dim,
                fontSize: isMobile ? 10 : 11, fontFamily: "monospace", cursor: inst.active ? "pointer" : "default",
                letterSpacing: "0.1em", transition: "all 0.2s", whiteSpace: "nowrap",
                opacity: inst.active ? 1 : 0.4,
              }}>
              {inst.label}
              <span style={{ fontSize: 8, color: T.dark, marginLeft: 6 }}>{inst.sublabel}</span>
              {!inst.active && <span style={{ fontSize: 7, color: T.dark, marginLeft: 4 }}>СКОРО</span>}
            </button>
          ))}

          {/* Spacer + nav tabs */}
          <div style={{ flex: "0 0 auto", display: "flex", marginLeft: "auto" }}>
            {["dashboard", "history"].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                style={{
                  padding: isMobile ? "8px 10px" : "10px 16px",
                  background: "transparent",
                  borderBottom: activeTab === tab ? `2px solid ${T.accent}` : "2px solid transparent",
                  border: "none",
                  color: activeTab === tab ? T.accent : T.dark,
                  fontSize: isMobile ? 9 : 10, fontFamily: "monospace", cursor: "pointer",
                  letterSpacing: "0.1em", transition: "all 0.2s",
                }}>
                {tab === "dashboard" ? "📊" : "📋"}{!isMobile && (tab === "dashboard" ? " ДАШБОРД" : " ІСТОРІЯ")}
              </button>
            ))}
          </div>
        </div>

        {/* ── DIESEL PLACEHOLDER ── */}
        {instrument === "diesel" && (
          <div style={{ textAlign: "center", padding: isMobile ? "40px 16px" : "80px 20px" }}>
            <div style={{ fontSize: isMobile ? 28 : 40, marginBottom: 16 }}>⛽</div>
            <div style={{ fontSize: isMobile ? 14 : 18, color: T.accent, fontWeight: 700, marginBottom: 8 }}>
              ДИЗЕЛЬ УКРАЇНА — ОПТ
            </div>
            <div style={{ fontSize: isMobile ? 11 : 13, color: T.dim, maxWidth: 400, margin: "0 auto", lineHeight: 1.6 }}>
              Моніторинг оптових цін на дизпаливо в Україні.
              Джерела: UPECO, Enkorr, НБУ.
            </div>
            <div style={{ fontSize: 10, color: T.dark, marginTop: 20, letterSpacing: "0.15em" }}>
              [ В РОЗРОБЦІ ]
            </div>
          </div>
        )}

        {/* ── HISTORY TAB ── */}
        {instrument === "brent" && activeTab === "history" && (
          <div style={{ paddingTop: 12 }}>
            <HistoryPanel theme={T} daily={historyData.daily} digests={historyData.digests}
              agentHistory={historyData.agentHistory} loading={historyData.loading} onRefresh={historyData.refetch} isMobile={isMobile} />
          </div>
        )}

        {/* ── DASHBOARD ── */}
        {instrument === "brent" && activeTab === "dashboard" && (
          <div style={isMobile
            ? { display: "flex", flexDirection: "column", gap: 10, paddingTop: 10, paddingBottom: 20 }
            : { display: "grid", gridTemplateColumns: "1fr 295px", gap: 12, paddingTop: 12 }
          }>

            {/* ── LEFT / MAIN ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: isMobile ? 8 : 12 }}>

              {/* FORECAST */}
              <div style={{ background: T.panel, border: `1px solid ${mainColor}`,
                padding: isMobile ? "14px" : "18px 22px",
                boxShadow: `0 0 25px ${mainColor}18, inset 0 0 50px ${mainColor}04` }}>
                <div style={{ position: "absolute", top: 0, left: "8%", right: "8%", height: 1,
                  background: `linear-gradient(90deg, transparent, ${mainColor}, transparent)` }} />

                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <div style={{ width: 6, height: 6, background: mainColor, boxShadow: `0 0 10px ${mainColor}` }} />
                  <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.15em" }}>ПРОГНОЗ · 12 ГОД</span>
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: isMobile ? 20 : 28, fontWeight: 900, fontFamily: "monospace", lineHeight: 1.1,
                      color: mainColor, textShadow: `0 0 16px ${mainColor}`,
                      letterSpacing: "0.02em" }}>
                      {forecast ? (isBull ? "▲ ЗРОСТАННЯ" : isBear ? "▼ ПАДІННЯ" : "— НЕВИЗНАЧЕНО") : "⏳ ОЧІКУВАННЯ..."}
                    </div>
                    {forecast && (
                      <div style={{ fontSize: isMobile ? 10 : 12, color: T.dim, marginTop: 8, fontFamily: "monospace", lineHeight: 1.6 }}>
                        Ціль: ${forecast.target_price?.toFixed(2)} · Стоп: ${forecast.stop_loss_price?.toFixed(2) || "—"}
                      </div>
                    )}
                  </div>
                  <div style={{ flexShrink: 0, textAlign: "center" }}>
                    <ConfidenceGauge value={confPct} color={mainColor} size={isMobile ? 56 : 70} />
                  </div>
                </div>

                {drivers.length > 0 && (
                  <div style={{ display: "flex", gap: 4, marginTop: 10, flexWrap: "wrap" }}>
                    {drivers.slice(0, isMobile ? 3 : 4).map((f, i) => (
                      <span key={i} style={{ fontSize: 8, color: T.dim, background: `${T.accent}08`,
                        border: `1px solid ${T.dark}`, padding: "2px 6px", fontFamily: "monospace",
                        maxWidth: isMobile ? 150 : 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {f.slice(0, isMobile ? 30 : 40)}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* CHART */}
              <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: isMobile ? "10px" : "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <div>
                    <div style={{ fontSize: 9, color: T.dark }}>BZ=F · 1 ГОД.</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: T.dim, fontFamily: "monospace" }}>Brent Crude</div>
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: brentChange >= 0 ? T.accent : "#ff4444",
                    textShadow: `0 0 8px ${brentChange >= 0 ? T.accent : "#ff4444"}`, fontFamily: "monospace" }}>
                    ${brentPrice.toFixed(2)}
                  </div>
                </div>
                <MiniChart data={brentData} accent={T.accent} />
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 8, color: T.dark, fontFamily: "monospace" }}>
                  <span>МІН ${Math.min(...brentData.map(d => d.p)).toFixed(2)}</span>
                  <span>МАКС ${Math.max(...brentData.map(d => d.p)).toFixed(2)}</span>
                </div>
              </div>

              {/* RISK */}
              <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: isMobile ? "10px" : "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                  marginBottom: riskCollapsed ? 0 : 10, cursor: "pointer" }}
                  onClick={() => setRiskCollapsed(r => !r)}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 3, height: 10, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                    <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.15em" }}>РИЗИК</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 18, fontWeight: 900, color: composite > 0.6 ? "#ff4444" : "#ffaa00", fontFamily: "monospace" }}>
                      {compositeDisplay}<span style={{ fontSize: 10, color: T.dark }}>/10</span>
                    </span>
                    <span style={{ color: T.dark, fontSize: 10 }}>{riskCollapsed ? "+" : "−"}</span>
                  </div>
                </div>
                <div style={{ maxHeight: riskCollapsed ? 0 : 200, overflow: "hidden", transition: "max-height 0.35s ease" }}>
                  <div style={{ display: "grid", gridTemplateColumns: isMobile ? "repeat(2, 1fr)" : "repeat(3, 1fr)", gap: "6px 14px" }}>
                    {riskItems.map(r => {
                      const val = Math.round(r.v * 10);
                      return (
                        <div key={r.l}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                            <span style={{ fontSize: 8, color: T.dark }}>{r.l.toUpperCase()}</span>
                            <span style={{ fontSize: 8, color: val >= 7 ? "#ff4444" : val >= 5 ? "#ffaa00" : T.accent, fontFamily: "monospace" }}>{val}/10</span>
                          </div>
                          <div style={{ height: 2, background: T.darker }}>
                            <div style={{ height: 2, width: `${val * 10}%`, transition: "width 0.4s",
                              background: val >= 7 ? "#ff4444" : val >= 5 ? "#ffaa00" : T.accent }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* AGENTS (mobile: inline, desktop: in sidebar) */}
              {isMobile && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.15em", paddingTop: 2 }}>AI РАДА</div>
                  {agentNames.map(name => (
                    <AgentCard key={name} name={name} agentData={agents[name]} theme={theme} visible={agentsVisible} isMobile={isMobile} />
                  ))}
                </div>
              )}

              {/* SIGNAL HISTORY */}
              <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: isMobile ? "10px" : "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 3, height: 10, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                    <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.15em" }}>СИГНАЛИ</span>
                  </div>
                  <span style={{ fontSize: 9, color: T.dim, fontFamily: "monospace" }}>{signals.length}</span>
                </div>
                {!isMobile && (
                  <div style={{ display: "grid", gridTemplateColumns: "48px 1fr 100px 72px 50px", gap: 10, marginBottom: 4 }}>
                    {["ЧАС", "СИГНАЛ", "КОНСЕНСУС", "ЦІНА", "ВПЕВН."].map(h => (
                      <span key={h} style={{ fontSize: 7, color: T.darker, letterSpacing: "0.1em" }}>{h}</span>
                    ))}
                  </div>
                )}
                {signals.length === 0 && (
                  <div style={{ textAlign: "center", padding: 16, fontSize: 10, color: T.dark }}>Очікування сигналу...</div>
                )}
                {signals.slice(0, isMobile ? 6 : 10).map((s, i) => (
                  <SignalRow key={`${s.time}-${i}`} s={s} idx={i} theme={theme} isNew={i === 0} isMobile={isMobile} />
                ))}
              </div>

              {/* EVENTS (mobile: here, desktop: sidebar) */}
              {isMobile && events.length > 0 && (
                <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <div style={{ width: 3, height: 10, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                    <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.15em" }}>ПОДІЇ</span>
                  </div>
                  {events.slice(0, 3).map((e, i) => (
                    <div key={i} style={{ padding: "6px 0", borderBottom: `1px solid ${T.darker}` }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 10, color: T.dim, fontFamily: "monospace" }}>{e.name}</span>
                        <span style={{ fontSize: 8, color: e.impact_level === "high" ? "#ff4444" : "#ffaa00" }}>
                          {eventImpactMap[e.impact_level] || e.impact_level}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── RIGHT SIDEBAR (desktop only) ── */}
            {!isMobile && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.15em", paddingTop: 2 }}>AI РАДА</div>
                {agentNames.map(name => (
                  <AgentCard key={name} name={name} agentData={agents[name]} theme={theme} visible={agentsVisible} isMobile={false} />
                ))}

                {/* EVENTS */}
                <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <div style={{ width: 3, height: 10, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                    <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.15em" }}>ЗАПЛАНОВАНІ ПОДІЇ</span>
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

                {/* CONNECTION */}
                <div style={{ background: T.panel, border: `1px solid ${wsConnected ? T.accent + "44" : "#ff444444"}`, padding: "10px 14px",
                  display: "flex", alignItems: "center", gap: 10 }}>
                  <span>{wsConnected ? "🟢" : "🔴"}</span>
                  <div>
                    <div style={{ fontSize: 10, color: wsConnected ? T.accent : "#ff4444", fontFamily: "monospace" }}>
                      {wsConnected ? "LIVE · WS" : "POLLING · REST"}
                    </div>
                  </div>
                </div>

                {/* Theme selector */}
                <div style={{ display: "flex", gap: 4, justifyContent: "center", padding: "4px 0" }}>
                  {Object.keys(THEMES).map(tk => (
                    <button key={tk} onClick={() => setTheme(tk)}
                      style={{ background: theme === tk ? `${THEMES[tk].accent}22` : "transparent",
                        border: `1px solid ${theme === tk ? THEMES[tk].accent : T.darker}`,
                        color: THEMES[tk].accent, fontSize: 8, padding: "2px 8px", fontFamily: "monospace",
                        cursor: "pointer", letterSpacing: "0.08em" }}>
                      {THEMES[tk].name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Accessibility */}
      <div aria-live="assertive" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", opacity: 0 }}>
        {`Прогноз: ${forecast?.direction || "очікування"}, впевненість ${confPct}%`}
      </div>

      {/* Global styles */}
      <style>{`
        @keyframes ticker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { margin: 0; overflow-x: hidden; }
      `}</style>
    </div>
  );
}
