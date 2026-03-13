import { useState, useEffect, useRef, useCallback } from "react";

// ─── ТЕМИ ───────────────────────────────────────────────────────────────────
const THEMES = {
  matrix:  { name: "МАТРИЦЯ",   accent: "#00ff41", dim: "#00aa2a", dark: "#005c1a", darker: "#001a06", bg: "#000800", panel: "rgba(0,8,0,0.85)" },
  amber:   { name: "БУРШТИН",   accent: "#ffb000", dim: "#cc8800", dark: "#664600", darker: "#2a1a00", bg: "#080400", panel: "rgba(8,4,0,0.85)" },
  cyber:   { name: "КІБЕРСИНІЙ",accent: "#00e5ff", dim: "#00aacc", dark: "#005966", darker: "#001a22", bg: "#000608", panel: "rgba(0,6,8,0.85)" },
};

// ─── ДАНІ ────────────────────────────────────────────────────────────────────
const MOCK_SIGNALS = [
  { time: "14:31", type: "СИЛЬНА КУПІВЛЯ", reason: "EIA бичачий сюрприз + ОПЕК підтверджує скорочення", consensus: "ОДНОСТАЙНО", price: 84.20, conf: 91 },
  { time: "11:15", type: "СЛАБКЕ УТРИМАННЯ", reason: "Геополітичний шум, дані змішані", consensus: "КОНФЛІКТ", price: 83.50, conf: 54 },
  { time: "09:02", type: "БЕЗ УГОДИ", reason: "Денний ліміт ризику вичерпано", consensus: "—", price: 82.10, conf: 0 },
  { time: "08:44", type: "ПРОДАЖ", reason: "МЕА переглянуло прогноз попиту вниз", consensus: "СИЛЬНО", price: 81.90, conf: 76 },
  { time: "07:20", type: "КУПІВЛЯ", reason: "Brent стрибнув на напрузі в Червоному морі", consensus: "СИЛЬНО", price: 80.60, conf: 82 },
];

const AGENTS = [
  { name: "Grok",        role: "Настрій ринку",    icon: "𝕏", status: "БИЧАЧИЙ",     detail: "Нафтові журналісти: +73% оптимістів",          expand: "X/Twitter: 847 постів за 4г. Sentiment score +0.73. Ключові автори: @elonmusk, @OilDrumHQ. Тренди: #OPECcut #BrentUp" },
  { name: "Perplexity",  role: "Перевірка фактів",  icon: "⊕", status: "ПІДТВЕРДЖЕНО", detail: "EIA скорочення: −4.2M бар. підтверджено",         expand: "EIA звіт 13:30 ET: Commercial crude −4.2M bbl vs −1.8M прогноз. Cushing −0.8M. Distillates −1.1M. Gasoline +0.3M. Джерело: eia.gov/petroleum" },
  { name: "Gemini",      role: "Макроаналіз",       icon: "◈", status: "НЕЙТРАЛЬНО",  detail: "Сезонний попит на рівні середнього",               expand: "Q4 сезонність: +2.1% vs avg. DXY -0.4% цього тижня. Fed minutes: hawkish тон. China PMI 50.2 (exp 49.8). Спред WTI-Brent: $3.8" },
  { name: "Claude",      role: "Ризик-менеджер",    icon: "◆", status: "КУПУВАТИ",    detail: "Контанго звужується, ризик 6.2/10",                expand: "Brent M1-M2 спред: +$0.42 (зростання). Implied vol: 28.3%. OI зростає. Risk score: Geo(7) Sup(5) Dem(6) Fin(8) Sea(4) Tec(6) = 6.0/10" },
];

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
    const id = setInterval(() => {
      ctx.fillStyle = "rgba(0,0,0,0.05)"; ctx.fillRect(0, 0, c.width, c.height);
      for (let i = 0; i < drops.length; i++) {
        const ch = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
        ctx.fillStyle = Math.random() > 0.95 ? "#fff" : `rgba(0,${180+Math.floor(Math.random()*75)},${Math.floor(Math.random()*40)},${0.6+Math.random()*0.4})`;
        ctx.font = `${fs}px monospace`; ctx.fillText(ch, i * fs, drops[i] * fs);
        if (drops[i] * fs > c.height && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
      }
    }, 40);
    return () => { clearInterval(id); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} style={{ position: "fixed", top: 0, left: 0, zIndex: 0, opacity, pointerEvents: "none", transition: "opacity 0.5s" }} />;
}

// ─── MINI CHART ─────────────────────────────────────────────────────────────
function MiniChart({ data, accent, hovered, setHover }) {
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
        {filtered.map((c, i) => (
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

// ─── AGENT CARD ─────────────────────────────────────────────────────────────
function AgentCard({ agent, theme, visible, focusMode }) {
  const T = THEMES[theme];
  const [expanded, setExpanded] = useState(false);
  const statusColors = { "БИЧАЧИЙ": T.accent, "КУПУВАТИ": T.accent, "ПІДТВЕРДЖЕНО": "#00ffcc", "НЕЙТРАЛЬНО": "#ffaa00", "ВЕДМЕЖИЙ": "#ff4444", "ПРОДАВАТИ": "#ff4444" };
  const sc = statusColors[agent.status] || T.dim;
  return (
    <div onClick={() => setExpanded(e => !e)}
      style={{ background: T.panel, border: `1px solid ${expanded ? T.accent : T.dark}`, padding: "12px 14px", cursor: "pointer",
        opacity: visible ? (focusMode ? 0.4 : 1) : 0, transform: visible ? "translateX(0)" : "translateX(10px)", transition: "all 0.35s ease",
        boxShadow: expanded ? `0 0 12px ${T.accent}22` : "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14, color: T.accent, textShadow: `0 0 8px ${T.accent}` }}>{agent.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.accent, fontFamily: "monospace", textShadow: `0 0 6px ${T.accent}88` }}>{agent.name}</div>
          <div style={{ fontSize: 9, color: T.dark, fontFamily: "monospace", letterSpacing: "0.06em" }}>{agent.role}</div>
        </div>
        <div style={{ fontSize: 9, fontWeight: 700, color: sc, fontFamily: "monospace", letterSpacing: "0.1em", textShadow: `0 0 6px ${sc}88` }}>{agent.status}</div>
        <span style={{ color: T.dark, fontSize: 10, marginLeft: 4 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      <div style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", marginTop: 6, borderLeft: `1px solid ${T.dark}`, paddingLeft: 8 }}>{agent.detail}</div>
      <div style={{ maxHeight: expanded ? 120 : 0, overflow: "hidden", transition: "max-height 0.3s ease" }}>
        <div style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", marginTop: 10, padding: "8px 10px",
          background: T.darker, borderLeft: `2px solid ${T.accent}`, lineHeight: 1.7 }}>
          {agent.expand}
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
  const colors = { "СИЛЬНА КУПІВЛЯ": T.accent, "КУПІВЛЯ": T.dim, "СЛАБКЕ УТРИМАННЯ": "#ffaa00", "БЕЗ УГОДИ": T.dark, "ПРОДАЖ": "#ff4444" };
  const consensusStyle = {
    "ОДНОСТАЙНО": { bg: T.accent, color: "#000", weight: 900 },
    "КОНФЛІКТ": { bg: "transparent", color: "#ffaa00", weight: 700, border: "1px dashed #ffaa00" },
  }[s.consensus] || { bg: "transparent", color: T.dark };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "48px 1fr 100px 72px 50px", gap: 10,
      padding: "8px 0", borderBottom: `1px solid ${T.darker}`, alignItems: "center",
      opacity: Math.max(0.2, 1 - idx * 0.16),
      background: flash ? `${T.accent}18` : "transparent", transition: "background 0.5s ease" }}>
      <span style={{ fontSize: 10, color: T.dark, fontFamily: "monospace" }}>{s.time}</span>
      <div>
        <span style={{ fontSize: 10, fontWeight: 700, color: colors[s.type] || T.accent, fontFamily: "monospace", textShadow: `0 0 5px ${colors[s.type] || T.accent}88` }}>{s.type}</span>
        <div style={{ fontSize: 9, color: T.dark, fontFamily: "monospace", marginTop: 2, lineHeight: 1.4 }}>{s.reason}</div>
      </div>
      <div style={{ display: "flex", justifyContent: "center" }}>
        <span style={{ fontSize: 8, fontFamily: "monospace", padding: "2px 6px", background: consensusStyle.bg,
          color: consensusStyle.color, fontWeight: consensusStyle.weight, border: consensusStyle.border }}>
          {s.consensus}
        </span>
      </div>
      <span style={{ fontSize: 10, color: T.dim, fontFamily: "monospace", textAlign: "right" }}>${s.price.toFixed(2)}</span>
      <span style={{ fontSize: 10, fontFamily: "monospace", textAlign: "right",
        color: s.conf > 70 ? T.accent : s.conf > 40 ? "#ffaa00" : T.dark }}>
        {s.conf > 0 ? `${s.conf}%` : "—"}
      </span>
    </div>
  );
}

// ─── MAIN ────────────────────────────────────────────────────────────────────
export default function WarRoom() {
  const [theme, setTheme] = useState("matrix");
  const [focusMode, setFocusMode] = useState(false);
  const [rainOpacity, setRainOpacity] = useState(0.18);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [riskCollapsed, setRiskCollapsed] = useState(false);

  const [brentData, setBrentData] = useState(() => generatePriceData(82.0, 0.4));
  const [gasoilData, setGasoilData] = useState(() => generatePriceData(728.0, 1.8));
  const [brentPrice, setBrentPrice] = useState(84.20);
  const [brentChange, setBrentChange] = useState(+1.83);
  const [brentUpdated, setBrentUpdated] = useState(Date.now());
  const [gasoilPrice, setGasoilPrice] = useState(731.40);
  const [gasoilChange, setGasoilChange] = useState(+3.20);
  const [gasoilUpdated, setGasoilUpdated] = useState(Date.now());
  const [brentFlash, setBrentFlash] = useState(false);
  const [gasoilFlash, setGasoilFlash] = useState(false);
  const [latency, setLatency] = useState(98);
  const [time, setTime] = useState(new Date());
  const [agentsVisible, setAgentsVisible] = useState(false);
  const [glitch, setGlitch] = useState(false);
  const tickRef = useRef(0);

  const T = THEMES[theme];

  // Volatility-based "calm / alert" UI
  const volatility = Math.abs(brentChange);
  const isAlert = volatility > 2.5;

  // Keyboard: Cmd+K
  useEffect(() => {
    const h = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setPaletteOpen(p => !p); } if (e.key === "Escape") setPaletteOpen(false); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  useEffect(() => {
    const t = setInterval(() => {
      tickRef.current += 1;
      const now = new Date(); setTime(now);
      setLatency(Math.floor(80 + Math.random() * 120));

      setBrentPrice(p => {
        const n = +(p + (Math.random() - 0.49) * 0.09).toFixed(2);
        setBrentData(d => [...d.slice(1), { t: 0, p: n }]);
        setBrentUpdated(Date.now());
        setBrentFlash(true); setTimeout(() => setBrentFlash(false), 220);
        return n;
      });
      setBrentChange(c => +(c + (Math.random() - 0.5) * 0.03).toFixed(2));

      if (tickRef.current % 7 === 0) {
        setGasoilPrice(p => {
          const n = +(p + (Math.random() - 0.48) * 0.6).toFixed(2);
          setGasoilData(d => [...d.slice(1), { t: 0, p: n }]);
          setGasoilUpdated(Date.now());
          setGasoilFlash(true); setTimeout(() => setGasoilFlash(false), 220);
          return n;
        });
        setGasoilChange(c => +(c + (Math.random() - 0.5) * 0.1).toFixed(2));
      }
    }, 2000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => { setTimeout(() => setAgentsVisible(true), 400); }, []);

  // Glitch on forecast
  useEffect(() => {
    const g = setInterval(() => { setGlitch(true); setTimeout(() => setGlitch(false), 120); }, 5000);
    return () => clearInterval(g);
  }, []);

  const forecast = { direction: "UP", confidence: 91, consensus: "ОДНОСТАЙНО · 4/4",
    summary: "EIA зафіксував зниження запасів на 4.2M барелів. ОПЕК утримує скорочення. Долар слабшає. Ціль: $86.50.",
    factors: ["EIA −4.2M БАР.", "ОПЕК СКОРОЧУЄ", "ДОЛАР СЛАБШАЄ", "РИЗИК 6.2/10", "СЕЗОННА ПІДТРИМКА"] };
  const isBull = forecast.direction === "UP";
  const mainColor = isBull ? T.accent : "#ff4444";

  const latColor = latency < 200 ? T.accent : latency < 500 ? "#ffaa00" : "#ff4444";
  const nowStr = (ts) => new Date(ts).toLocaleTimeString("uk-UA");

  const secOpacity = focusMode ? 0.2 : 1;

  // Ticker content
  const tickerItems = [`BRENT ${brentPrice.toFixed(2)} ${brentChange >= 0 ? "▲" : "▼"}${Math.abs(brentChange).toFixed(2)}`, `GASOIL ${gasoilPrice.toFixed(2)} ${gasoilChange >= 0 ? "▲" : "▼"}${Math.abs(gasoilChange).toFixed(2)}`, "РИЗИК 6.2/10", "ТОЧНІСТЬ 74%", "УГОД 2/3", "КОНСЕНСУС: ОДНОСТАЙНО"].join("  ·  ");

  return (
    <div style={{ background: T.bg, minHeight: "100vh", color: T.accent, fontFamily: "monospace", overflow: "hidden" }}>
      <MatrixRain opacity={rainOpacity} />

      {/* Scanlines */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1,
        backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.07) 3px, rgba(0,0,0,0.07) 4px)" }} />

      {/* Alert overlay */}
      {isAlert && <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1,
        border: `2px solid ${T.accent}66`, boxShadow: `inset 0 0 60px ${T.accent}08`, animation: "none" }} />}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
        theme={theme} setTheme={setTheme} focusMode={focusMode} setFocusMode={setFocusMode}
        rainOpacity={rainOpacity} setRainOpacity={setRainOpacity} />

      <div style={{ position: "relative", zIndex: 2, maxWidth: 1400, margin: "0 auto", padding: "0 14px" }}>

        {/* ── ВЕРХНЯ ПАНЕЛЬ ── */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 0", borderBottom: `1px solid ${T.dark}`, position: "sticky", top: 0, zIndex: 20,
          background: T.bg, backdropFilter: "blur(8px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 900, letterSpacing: "0.2em", color: T.accent, textShadow: `0 0 12px ${T.accent}` }}>
              🛢 НАФТОВА_РАДА.EXE
            </span>
            <div style={{ width: 6, height: 6, background: T.accent, boxShadow: `0 0 10px ${T.accent}` }} />
            <span style={{ fontSize: 9, color: T.accent, letterSpacing: "0.2em" }}>[ СИСТЕМА АКТИВНА ]</span>
          </div>

          <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
            {[
              { label: "БРЕНТ BZ=F", price: brentPrice, change: brentChange, flash: brentFlash },
              { label: "ГАЗОЙЛЬ LGO", price: gasoilPrice, change: gasoilChange, flash: gasoilFlash },
            ].map((item) => (
              <div key={item.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.15em" }}>{item.label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "monospace",
                  color: item.change >= 0 ? T.accent : "#ff4444",
                  textShadow: `0 0 ${item.flash ? "18px" : "8px"} ${item.change >= 0 ? T.accent : "#ff4444"}`,
                  transition: "text-shadow 0.25s ease" }}>
                  ${item.price.toFixed(2)}
                </div>
                <div style={{ fontSize: 10, color: item.change >= 0 ? T.dim : "#cc3333", fontFamily: "monospace" }}>
                  {item.change >= 0 ? "▲" : "▼"} {Math.abs(item.change).toFixed(2)}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <div style={{ fontSize: 9, fontFamily: "monospace", color: latColor }}>
              ЗАТРИМКА: {latency}мс
            </div>
            <button onClick={() => setPaletteOpen(true)}
              style={{ background: "none", border: `1px solid ${T.dark}`, color: T.dim, fontSize: 9, padding: "3px 8px",
                fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.1em" }}>
              ⌘ КОМАНДИ
            </button>
            <div style={{ fontSize: 11, color: T.dark, letterSpacing: "0.1em" }}>{time.toLocaleTimeString("uk-UA")}</div>
          </div>
        </div>

        {/* ── TICKER СТРІЧКА ── */}
        <div style={{ overflow: "hidden", borderBottom: `1px solid ${T.darker}`, background: T.darker }}>
          <div style={{ display: "inline-block", whiteSpace: "nowrap", animation: "ticker 25s linear infinite",
            fontSize: 9, color: T.dim, padding: "5px 0", letterSpacing: "0.1em" }}>
            {tickerItems}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{tickerItems}
          </div>
        </div>
        <style>{`@keyframes ticker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }`}</style>

        {/* ── ОСНОВНА СІТКА ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 295px", gap: 12, paddingTop: 12 }}>

          {/* ── ЛІВА ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

            {/* ПРОГНОЗ — STICKY */}
            <div style={{ position: "sticky", top: 57, zIndex: 10,
              background: T.panel, border: `1px solid ${mainColor}`,
              padding: "18px 22px", boxShadow: `0 0 ${isAlert ? "50px" : "25px"} ${mainColor}18, inset 0 0 50px ${mainColor}04`,
              transition: "box-shadow 1.5s ease" }}>
              {/* Top glow line */}
              <div style={{ position: "absolute", top: 0, left: "8%", right: "8%", height: 1,
                background: `linear-gradient(90deg, transparent, ${mainColor}, transparent)` }} />
              {/* Corner accents */}
              {[[{top:0,left:0},{borderTop:`1px solid ${mainColor}`,borderLeft:`1px solid ${mainColor}`}],
                [{top:0,right:0},{borderTop:`1px solid ${mainColor}`,borderRight:`1px solid ${mainColor}`}],
                [{bottom:0,left:0},{borderBottom:`1px solid ${mainColor}`,borderLeft:`1px solid ${mainColor}`}],
                [{bottom:0,right:0},{borderBottom:`1px solid ${mainColor}`,borderRight:`1px solid ${mainColor}`}]
              ].map(([pos, b], i) => <div key={i} style={{ position:"absolute", width:10, height:10, ...pos, ...b }} />)}

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
                    {isBull ? "▲ ЦІНА ЗРОСТАТИМЕ" : "▼ ЦІНА ПАДАТИМЕ"}
                  </div>
                  <div style={{ fontSize: 12, color: T.dim, marginTop: 10, fontFamily: "monospace",
                    lineHeight: 1.7, maxWidth: 440, borderLeft: `2px solid ${T.dark}`, paddingLeft: 12 }}>
                    {forecast.summary}
                  </div>
                </div>

                <div style={{ flexShrink: 0, borderLeft: `1px solid ${T.dark}`, paddingLeft: 18, textAlign: "center" }}>
                  <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.15em", marginBottom: 4 }}>ВПЕВНЕНІСТЬ</div>
                  <ConfidenceGauge value={forecast.confidence} color={mainColor} />
                  <div style={{ fontSize: 9, color: T.dim, marginTop: 4, letterSpacing: "0.1em" }}>{forecast.consensus}</div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
                {forecast.factors.map((f, i) => (
                  <span key={i} style={{ fontSize: 9, color: T.dim, background: `${T.accent}08`,
                    border: `1px solid ${T.dark}`, padding: "3px 8px", fontFamily: "monospace", letterSpacing: "0.1em" }}>
                    [{f}]
                  </span>
                ))}
              </div>
            </div>

            {/* ГРАФІКИ */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, opacity: focusMode ? 0.7 : 1, transition: "opacity 0.4s" }}>
              {[
                { title: "Нафта Brent", ticker: "BZ=F · 1 ГОД.", price: brentPrice, change: brentChange, data: brentData, updated: brentUpdated, freq: "~2с" },
                { title: "Газойль London", ticker: "LGO · 1 ГОД.", price: gasoilPrice, change: gasoilChange, data: gasoilData, updated: gasoilUpdated, freq: "~15с" },
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
                      <div style={{ fontSize: 10, color: c.change >= 0 ? T.dim : "#cc3333", fontFamily: "monospace" }}>
                        {c.change >= 0 ? "▲" : "▼"} {Math.abs(c.change).toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <MiniChart data={c.data} accent={T.accent} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9, color: T.dark, fontFamily: "monospace" }}>
                    <span>МІН ${Math.min(...c.data.map(d => d.p)).toFixed(2)}</span>
                    <span>↻ {c.freq} · {nowStr(c.updated)}</span>
                    <span>МАКС ${Math.max(...c.data.map(d => d.p)).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* РИЗИК */}
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px", opacity: focusMode ? 0.2 : 1, transition: "opacity 0.4s" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: riskCollapsed ? 0 : 12, cursor: "pointer" }}
                onClick={() => setRiskCollapsed(r => !r)}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                  <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>РИЗИК-КОНТРОЛЬ</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span style={{ fontSize: 22, fontWeight: 900, color: "#ffaa00", textShadow: "0 0 10px #ffaa00", fontFamily: "monospace" }}>6.2<span style={{ fontSize: 11, color: T.dark }}>/10</span></span>
                  <span style={{ fontSize: 9, color: T.dark }}>УГОД: <span style={{ color: T.accent }}>2/3</span></span>
                  <span style={{ color: T.dark, fontSize: 11 }}>{riskCollapsed ? "[+]" : "[−]"}</span>
                </div>
              </div>
              <div style={{ maxHeight: riskCollapsed ? 0 : 200, overflow: "hidden", transition: "max-height 0.35s ease" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px 18px" }}>
                  {[{ l: "Геополітика", v: 7 }, { l: "Пропозиція", v: 5 }, { l: "Попит", v: 6 }, { l: "Фінанси", v: 8 }, { l: "Сезонність", v: 4 }, { l: "Технічний", v: 6 }].map(r => (
                    <div key={r.l}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                        <span style={{ fontSize: 8, color: T.dark, letterSpacing: "0.08em" }}>{r.l.toUpperCase()}</span>
                        <span style={{ fontSize: 8, color: r.v >= 7 ? "#ff4444" : r.v >= 5 ? "#ffaa00" : T.accent, fontFamily: "monospace" }}>{r.v}/10</span>
                      </div>
                      <div style={{ height: 2, background: T.darker }}>
                        <div style={{ height: 2, width: `${r.v * 10}%`, transition: "width 0.4s",
                          background: r.v >= 7 ? "#ff4444" : r.v >= 5 ? "#ffaa00" : T.accent,
                          boxShadow: `0 0 4px ${r.v >= 7 ? "#ff4444" : r.v >= 5 ? "#ffaa00" : T.accent}` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* СТРІЧКА СИГНАЛІВ */}
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px", opacity: focusMode ? 0.2 : 1, transition: "opacity 0.4s" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                  <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ІСТОРІЯ ПРОГНОЗІВ</span>
                </div>
                <span style={{ fontSize: 9, color: T.dim, fontFamily: "monospace" }}>ТОЧНІСТЬ: <span style={{ color: T.accent }}>74% ↑</span></span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "48px 1fr 100px 72px 50px", gap: 10, marginBottom: 6 }}>
                {["ЧАС", "СИГНАЛ", "КОНСЕНСУС", "ЦІНА", "ВПЕВН."].map(h => (
                  <span key={h} style={{ fontSize: 8, color: T.darker, letterSpacing: "0.12em" }}>{h}</span>
                ))}
              </div>
              {MOCK_SIGNALS.map((s, i) => <SignalRow key={i} s={s} idx={i} theme={theme} isNew={i === 0} />)}
            </div>
          </div>

          {/* ── ПРАВА ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 9, color: T.dark, letterSpacing: "0.2em", paddingTop: 2 }}>// СТАТУС AI РАДИ</div>
            {AGENTS.map(a => <AgentCard key={a.name} agent={a} theme={theme} visible={agentsVisible} focusMode={focusMode} />)}

            {/* ПОДІЇ */}
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px", opacity: secOpacity, transition: "opacity 0.4s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ЗАПЛАНОВАНІ ПОДІЇ</span>
              </div>
              {[
                { name: "Звіт EIA по запасах", time: "Ср 10:30 ET", impact: "КРИТИЧНО" },
                { name: "API Запаси нафти", time: "Сьогодні 16:30 ET", impact: "СЕРЕДНЬО" },
                { name: "Baker Hughes — бурові", time: "Пт 13:00 ET", impact: "СЕРЕДНЬО" },
              ].map(e => (
                <div key={e.name} style={{ padding: "7px 0", borderBottom: `1px solid ${T.darker}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 10, color: T.dim, fontFamily: "monospace" }}>{e.name}</span>
                    <span style={{ fontSize: 8, color: e.impact === "КРИТИЧНО" ? "#ff4444" : "#ffaa00", letterSpacing: "0.1em" }}>{e.impact}</span>
                  </div>
                  <div style={{ fontSize: 9, color: T.dark, marginTop: 2 }}>{e.time}</div>
                </div>
              ))}
            </div>

            {/* TELEGRAM */}
            <div style={{ background: T.panel, border: `1px solid #00aaff44`, padding: "10px 14px",
              display: "flex", alignItems: "center", gap: 10, opacity: secOpacity, transition: "opacity 0.4s" }}>
              <span>✈️</span>
              <div>
                <div style={{ fontSize: 10, color: "#00aaff", fontFamily: "monospace", letterSpacing: "0.1em", textShadow: "0 0 6px #00aaff88" }}>TELEGRAM СПОВІЩЕННЯ</div>
                <div style={{ fontSize: 9, color: T.dark, marginTop: 2 }}>АКТИВНО · ОСТАННЄ: 14:31</div>
              </div>
              <div style={{ marginLeft: "auto", width: 7, height: 7, background: T.accent, boxShadow: `0 0 8px ${T.accent}` }} />
            </div>

            {/* Поточна тема */}
            <div style={{ fontSize: 8, color: T.dark, textAlign: "center", letterSpacing: "0.15em", padding: "4px 0" }}>
              ТЕМА: {THEMES[theme].name} · ⌘K — КОМАНДИ
            </div>
          </div>
        </div>
      </div>

      {/* Aria live region */}
      <div aria-live="assertive" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", opacity: 0 }}>
        {`Прогноз: ${isBull ? "зростання" : "падіння"}, впевненість ${forecast.confidence}%`}
      </div>
    </div>
  );
}
