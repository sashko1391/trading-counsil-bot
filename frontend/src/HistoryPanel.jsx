import { useState, useMemo, useCallback } from "react";

const TREND_UA = { LONG: "ЗРОСТ", SHORT: "ПАД", WAIT: "НЕЙТР" };
const TREND_COLOR = { LONG: "#00ff41", SHORT: "#ff4444", WAIT: "#ffaa00" };
const AGENT_ICONS = { grok: "𝕏", perplexity: "⊕", gemini: "◈", claude: "◆" };

// ─── TREND CHART (SVG) ──────────────────────────────────────────────────────
function TrendChart({ data, theme }) {
  if (!data || data.length === 0) return null;

  const W = 700, H = 140, PAD = 40;
  const chartW = W - PAD * 2;
  const chartH = H - 30;

  // Extract confidence values and trends
  const confs = data.map(d => d.avg_confidence || 0);
  const maxConf = Math.max(...confs, 0.01);

  const points = data.map((d, i) => {
    const x = PAD + (i / Math.max(data.length - 1, 1)) * chartW;
    const y = chartH - (d.avg_confidence / maxConf) * (chartH - 10) + 5;
    return { x, y, d };
  });

  const polyline = points.map(p => `${p.x},${p.y}`).join(" ");
  const area = `M ${PAD},${chartH} L ${points.map(p => `${p.x},${p.y}`).join(" L ")} L ${PAD + chartW},${chartH} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }}>
      {/* Grid lines */}
      {[0.25, 0.5, 0.75, 1].map(v => {
        const y = chartH - (v / maxConf) * (chartH - 10) + 5;
        return (
          <g key={v}>
            <line x1={PAD} y1={y} x2={W - PAD} y2={y} stroke={theme.darker} strokeWidth="0.5" strokeDasharray="3,3" />
            <text x={PAD - 4} y={y + 3} fill={theme.dark} fontSize="7" textAnchor="end" fontFamily="monospace">
              {Math.round(v * 100)}%
            </text>
          </g>
        );
      })}

      {/* Area fill */}
      <path d={area} fill={`${theme.accent}08`} />

      {/* Confidence line */}
      <polyline points={polyline} fill="none" stroke={theme.accent} strokeWidth="1.5" strokeLinejoin="round" opacity="0.6" />

      {/* Trend dots */}
      {points.map((p, i) => {
        const color = TREND_COLOR[p.d.dominant_trend || p.d.trend] || theme.dim;
        return (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="4" fill={color} opacity="0.9"
              style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
            {/* Date labels (sparse) */}
            {(i === 0 || i === data.length - 1 || i % Math.max(1, Math.floor(data.length / 6)) === 0) && (
              <text x={p.x} y={H - 2} fill={theme.dark} fontSize="7" textAnchor="middle" fontFamily="monospace">
                {(p.d.date || p.d.timestamp || "").slice(5, 10)}
              </text>
            )}
          </g>
        );
      })}

      {/* Legend */}
      {[
        { label: "ЗРОСТ", color: "#00ff41", x: W - 160 },
        { label: "ПАД", color: "#ff4444", x: W - 115 },
        { label: "НЕЙТР", color: "#ffaa00", x: W - 80 },
      ].map(l => (
        <g key={l.label}>
          <circle cx={l.x} cy={8} r="3" fill={l.color} />
          <text x={l.x + 6} y={10} fill={theme.dim} fontSize="7" fontFamily="monospace">{l.label}</text>
        </g>
      ))}
    </svg>
  );
}

// ─── DAILY SUMMARY ROW ──────────────────────────────────────────────────────
function DailyRow({ d, theme, expanded, onToggle }) {
  const trend = TREND_UA[d.dominant_trend] || d.dominant_trend;
  const tColor = TREND_COLOR[d.dominant_trend] || theme.dim;
  const conf = Math.round((d.avg_confidence || 0) * 100);

  return (
    <div style={{ borderBottom: `1px solid ${theme.darker}` }}>
      <div onClick={onToggle} style={{
        display: "grid", gridTemplateColumns: "70px 60px 40px 70px 50px 1fr", gap: 8,
        padding: "8px 0", alignItems: "center", cursor: "pointer",
      }}>
        <span style={{ fontSize: 10, color: theme.dim, fontFamily: "monospace" }}>{d.date}</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: tColor, fontFamily: "monospace" }}>{trend}</span>
        <span style={{ fontSize: 10, color: conf > 50 ? theme.accent : theme.dark, fontFamily: "monospace" }}>{conf}%</span>
        <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace" }}>
          {d.total_events || 0} подій
        </span>
        <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace" }}>
          {d.digest_count || 0} дайдж
        </span>
        <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
          {d.closing_price > 0 && (
            <span style={{ fontSize: 10, color: theme.dim, fontFamily: "monospace" }}>
              ${d.closing_price?.toFixed(2)}
              {d.price_change_pct !== 0 && (
                <span style={{ color: d.price_change_pct > 0 ? "#00ff41" : "#ff4444", marginLeft: 4 }}>
                  {d.price_change_pct > 0 ? "+" : ""}{d.price_change_pct?.toFixed(1)}%
                </span>
              )}
            </span>
          )}
          <span style={{ color: theme.dark, fontSize: 9 }}>{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && (
        <div style={{ padding: "0 0 10px 12px", borderLeft: `2px solid ${tColor}`, marginLeft: 4 }}>
          {/* Action breakdown */}
          <div style={{ display: "flex", gap: 12, marginBottom: 6 }}>
            {["LONG", "SHORT", "WAIT"].map(a => (
              <span key={a} style={{ fontSize: 9, color: TREND_COLOR[a] || theme.dark, fontFamily: "monospace" }}>
                {a}: {d.action_counts?.[a] || 0}
              </span>
            ))}
            <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace" }}>
              змін тренду: {d.trend_changes || 0}
            </span>
          </div>
          {/* Agent dominants */}
          {d.agent_dominants && Object.keys(d.agent_dominants).length > 0 && (
            <div style={{ display: "flex", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
              {Object.entries(d.agent_dominants).map(([agent, action]) => (
                <span key={agent} style={{
                  fontSize: 8, fontFamily: "monospace", padding: "2px 6px",
                  border: `1px solid ${theme.dark}`, color: TREND_COLOR[action] || theme.dim,
                }}>
                  {AGENT_ICONS[agent] || "?"} {agent}: {action}
                </span>
              ))}
            </div>
          )}
          {/* Key theses */}
          {d.key_theses?.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {d.key_theses.slice(0, 3).map((t, i) => (
                <div key={i} style={{ fontSize: 9, color: theme.dim, fontFamily: "monospace", marginBottom: 3, lineHeight: 1.4 }}>
                  · {t}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── DIGEST ROW ─────────────────────────────────────────────────────────────
function DigestRow({ d, theme }) {
  const trend = TREND_UA[d.trend] || d.trend;
  const tColor = TREND_COLOR[d.trend] || theme.dim;
  const conf = Math.round((d.avg_confidence || 0) * 100);
  const time = (d.timestamp || "").slice(11, 16) || "—";
  const date = (d.timestamp || "").slice(0, 10);

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "42px 38px 50px 35px 1fr", gap: 8,
      padding: "6px 0", borderBottom: `1px solid ${theme.darker}`, alignItems: "center",
    }}>
      <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace" }}>{date.slice(5)}</span>
      <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace" }}>{time}</span>
      <span style={{ fontSize: 9, fontWeight: 700, color: tColor, fontFamily: "monospace" }}>{trend}</span>
      <span style={{ fontSize: 9, color: conf > 50 ? theme.accent : theme.dark, fontFamily: "monospace" }}>{conf}%</span>
      <div style={{ fontSize: 8, color: theme.dark, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {d.key_theses?.[0]?.slice(0, 80) || `${d.event_count || 0} подій`}
      </div>
    </div>
  );
}

// ─── AGENT MEMORY ROW ───────────────────────────────────────────────────────
function AgentMemoryRow({ entry, theme }) {
  const aColor = TREND_COLOR[entry.action] || theme.dim;
  const conf = Math.round((entry.confidence || 0) * 100);

  return (
    <div style={{ padding: "6px 0", borderBottom: `1px solid ${theme.darker}` }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace", minWidth: 40 }}>
          {(entry.timestamp || "").slice(5)}
        </span>
        <span style={{ fontSize: 9, color: theme.dark, fontFamily: "monospace", minWidth: 60 }}>
          {entry.event_type}
        </span>
        <span style={{ fontSize: 9, fontWeight: 700, color: aColor, fontFamily: "monospace", minWidth: 35 }}>
          {entry.action}
        </span>
        <span style={{ fontSize: 9, color: conf > 50 ? theme.accent : theme.dark, fontFamily: "monospace", minWidth: 28 }}>
          {conf}%
        </span>
      </div>
      <div style={{ fontSize: 9, color: theme.dim, fontFamily: "monospace", marginTop: 3, lineHeight: 1.4,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" }}>
        {entry.thesis}
      </div>
    </div>
  );
}

// ─── MAIN HISTORY PANEL ─────────────────────────────────────────────────────
export default function HistoryPanel({ theme, daily, digests, agentHistory, loading, onRefresh }) {
  const T = theme;
  const [subTab, setSubTab] = useState("daily");
  const [expandedDay, setExpandedDay] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState("grok");

  const tabs = [
    { key: "daily", label: "ЩОДЕННІ" },
    { key: "digests", label: "ДАЙДЖЕСТИ" },
    { key: "agents", label: "ПАМ'ЯТЬ АГЕНТІВ" },
  ];

  const agentEntries = useMemo(() => {
    return agentHistory?.[selectedAgent] || [];
  }, [agentHistory, selectedAgent]);

  const reversedDaily = useMemo(() => [...daily].reverse(), [daily]);
  const reversedDigests = useMemo(() => [...digests].reverse(), [digests]);
  const reversedAgentEntries = useMemo(() => [...agentEntries].reverse(), [agentEntries]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* SUB-TAB BAR */}
      <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${T.dark}` }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setSubTab(t.key)} style={{
            background: subTab === t.key ? `${T.accent}15` : "transparent",
            border: "none", borderBottom: subTab === t.key ? `2px solid ${T.accent}` : "2px solid transparent",
            color: subTab === t.key ? T.accent : T.dark,
            fontSize: 9, fontFamily: "monospace", letterSpacing: "0.12em",
            padding: "8px 16px", cursor: "pointer", transition: "all 0.2s",
          }}>
            {t.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={onRefresh} style={{
          background: "none", border: `1px solid ${T.dark}`, color: T.dim,
          fontSize: 9, fontFamily: "monospace", padding: "4px 10px", cursor: "pointer",
          marginBottom: 4, alignSelf: "center",
        }}>
          ↻ ОНОВИТИ
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 20, fontSize: 10, color: T.dark }}>
          Завантаження...
        </div>
      )}

      {/* DAILY TAB */}
      {subTab === "daily" && !loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Trend chart */}
          {daily.length > 0 && (
            <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
                <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>
                  ГРАФІК ТРЕНДІВ · {daily.length} ДНІВ
                </span>
              </div>
              <TrendChart data={daily} theme={T} />
            </div>
          )}

          {/* Daily list */}
          <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
              <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ЩОДЕННІ ЗВЕДЕННЯ</span>
              <span style={{ fontSize: 9, color: T.dark, marginLeft: "auto" }}>{daily.length} записів</span>
            </div>
            {/* Header */}
            <div style={{
              display: "grid", gridTemplateColumns: "70px 60px 40px 70px 50px 1fr", gap: 8,
              marginBottom: 4,
            }}>
              {["ДАТА", "ТРЕНД", "ВПЕВН", "ПОДІЇ", "ДАЙДЖ", "ЦІНА"].map(h => (
                <span key={h} style={{ fontSize: 7, color: T.darker, letterSpacing: "0.1em" }}>{h}</span>
              ))}
            </div>
            {daily.length === 0 && (
              <div style={{ textAlign: "center", padding: 20, fontSize: 10, color: T.dark }}>
                Ще немає щоденних зведень. Дані з'являться після першого повного дня роботи.
              </div>
            )}
            {reversedDaily.map((d, i) => (
              <DailyRow key={d.date || i} d={d} theme={T}
                expanded={expandedDay === (d.date || i)}
                onToggle={() => setExpandedDay(expandedDay === (d.date || i) ? null : (d.date || i))} />
            ))}
          </div>
        </div>
      )}

      {/* DIGESTS TAB */}
      {subTab === "digests" && !loading && (
        <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
            <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ІСТОРІЯ ДАЙДЖЕСТІВ (3-ГОДИННИХ)</span>
            <span style={{ fontSize: 9, color: T.dark, marginLeft: "auto" }}>{digests.length} записів</span>
          </div>

          {/* Digest mini chart */}
          {digests.length > 1 && (
            <div style={{ marginBottom: 12 }}>
              <TrendChart data={digests} theme={T} />
            </div>
          )}

          {/* Header */}
          <div style={{
            display: "grid", gridTemplateColumns: "42px 38px 50px 35px 1fr", gap: 8,
            marginBottom: 4,
          }}>
            {["ДАТА", "ЧАС", "ТРЕНД", "ВПЕВН", "ТЕЗА"].map(h => (
              <span key={h} style={{ fontSize: 7, color: T.darker, letterSpacing: "0.1em" }}>{h}</span>
            ))}
          </div>

          {digests.length === 0 && (
            <div style={{ textAlign: "center", padding: 20, fontSize: 10, color: T.dark }}>
              Ще немає дайджестів. Перший з'явиться через 3 години роботи бота.
            </div>
          )}
          {reversedDigests.map((d, i) => (
            <DigestRow key={d.timestamp || i} d={d} theme={T} />
          ))}
        </div>
      )}

      {/* AGENTS TAB */}
      {subTab === "agents" && !loading && (
        <div style={{ background: T.panel, border: `1px solid ${T.dark}`, padding: "12px 14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <div style={{ width: 3, height: 11, background: T.accent, boxShadow: `0 0 5px ${T.accent}` }} />
            <span style={{ fontSize: 9, color: T.dim, letterSpacing: "0.18em" }}>ПАМ'ЯТЬ АГЕНТІВ</span>
          </div>

          {/* Agent selector */}
          <div style={{ display: "flex", gap: 0, marginBottom: 12, borderBottom: `1px solid ${T.darker}` }}>
            {["grok", "perplexity", "claude", "gemini"].map(a => (
              <button key={a} onClick={() => setSelectedAgent(a)} style={{
                background: selectedAgent === a ? `${T.accent}15` : "transparent",
                border: "none", borderBottom: selectedAgent === a ? `2px solid ${T.accent}` : "2px solid transparent",
                color: selectedAgent === a ? T.accent : T.dark,
                fontSize: 9, fontFamily: "monospace", padding: "6px 12px", cursor: "pointer",
              }}>
                {AGENT_ICONS[a]} {a.charAt(0).toUpperCase() + a.slice(1)}
              </button>
            ))}
          </div>

          {/* Agent entries */}
          {agentEntries.length === 0 && (
            <div style={{ textAlign: "center", padding: 20, fontSize: 10, color: T.dark }}>
              Ще немає записів для {selectedAgent}. Дані з'являться після першого аналізу.
            </div>
          )}
          {reversedAgentEntries.map((e, i) => (
            <AgentMemoryRow key={e.timestamp || i} entry={e} theme={T} />
          ))}
        </div>
      )}
    </div>
  );
}
