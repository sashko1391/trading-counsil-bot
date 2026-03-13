#!/usr/bin/env bash
# =============================================================================
# ABAIC Phase 3A — Install & Test
# Copies Phase 3A files into your project and runs the full test suite.
#
# Usage:
#   bash install_phase3a.sh [path/to/your/project]
#   bash install_phase3a.sh          # uses current directory
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   ABAIC Phase 3A — Core Architecture Upgrade    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "📁 Project root: $PROJECT_ROOT"
echo ""

# Verify this looks like the right project
if [ ! -f "$PROJECT_ROOT/src/models/schemas.py" ] && [ ! -d "$PROJECT_ROOT/src" ]; then
    echo "⚠️  Warning: $PROJECT_ROOT/src not found."
    echo "   Make sure you're pointing to the ABAIC project root."
    read -p "   Continue anyway? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
fi

# Create directories if needed
mkdir -p "$PROJECT_ROOT/src/models"
mkdir -p "$PROJECT_ROOT/src/config"
mkdir -p "$PROJECT_ROOT/src/council"
mkdir -p "$PROJECT_ROOT/tests"
mkdir -p "$PROJECT_ROOT/data/knowledge"

echo "📋 Copying files..."

cp "$SCRIPT_DIR/src/models/schemas.py"           "$PROJECT_ROOT/src/models/schemas.py"
echo "   ✅ src/models/schemas.py          (v3.1 — extended schemas)"

cp "$SCRIPT_DIR/src/config/settings.py"          "$PROJECT_ROOT/src/config/settings.py"
echo "   ✅ src/config/settings.py         (v3.1 — new APIs + RSS + influencers + events)"

cp "$SCRIPT_DIR/src/config/prompts.py"           "$PROJECT_ROOT/src/config/prompts.py"
echo "   ✅ src/config/prompts.py          (v3.1 — Gemini historian + adversarial prompts)"

cp "$SCRIPT_DIR/src/council/adversarial_stage.py" "$PROJECT_ROOT/src/council/adversarial_stage.py"
echo "   ✅ src/council/adversarial_stage.py (NEW — Opus vs Gemini 3-step debate)"

cp "$SCRIPT_DIR/src/council/aggregator.py"       "$PROJECT_ROOT/src/council/aggregator.py"
echo "   ✅ src/council/aggregator.py      (v2 — weighted voting + devil's advocate)"

cp "$SCRIPT_DIR/tests/test_phase3a.py"           "$PROJECT_ROOT/tests/test_phase3a.py"
echo "   ✅ tests/test_phase3a.py          (38 tests)"

# Update .env.example only if it doesn't already have Phase 3A keys
if ! grep -q "OILPRICEAPI_KEY" "$PROJECT_ROOT/.env.example" 2>/dev/null; then
    cat >> "$PROJECT_ROOT/.env.example" << 'ENVAPPEND'

# ── Phase 3A additions ────────────────────────────────────────────────────────
OILPRICEAPI_KEY=           # OilPriceAPI.com ~$30/mo — Brent real-time
DATABENTO_API_KEY=         # Databento ~$1000/mo — ICE Brent + Gasoil (LGO)
NASDAQ_DATA_LINK_KEY=      # Quandl/Nasdaq — LGO historical (keep from Phase 1)
CLAUDE_OPUS_MODEL=claude-opus-4-6          # adversarial stage (expensive — only on STRONG signals)
CLAUDE_SONNET_MODEL=claude-sonnet-4-6      # council agent (cheaper)
GEMINI_MODEL=gemini-2.5-pro
ADVERSARIAL_ENABLED=true
MAX_PIPELINE_RUNS_PER_HOUR=5
RAG_NEWS_DECAY_LAMBDA=0.05
RAG_FACT_DECAY_LAMBDA=0.005
ENVAPPEND
    echo "   ✅ .env.example               (Phase 3A keys appended)"
fi

echo ""
echo "════════════════════════════════════════════════════"
echo "🧪 Running Phase 3A test suite..."
echo "════════════════════════════════════════════════════"
echo ""

cd "$PROJECT_ROOT"
python -m pytest tests/test_phase3a.py -v --tb=short 2>&1

echo ""
echo "════════════════════════════════════════════════════"
echo "✅ Phase 3A complete!"
echo ""
echo "What's new:"
echo "  📐 Extended schemas: HistoricalAnalogue, AdversarialResult,"
echo "     ProbabilityDensity, MarketRegime, AgentPerformanceRecord"
echo ""
echo "  ⚔️  Adversarial Stage: Opus 4.6 primary → Gemini counter"
echo "     (blind) → Opus final verdict. Anti-sycophancy by design."
echo ""
echo "  🗳️  Aggregator v2: confidence-weighted voting, devil's advocate"
echo "     (5th agent at 0.15 weight), dynamic weight support"
echo ""
echo "  📅 Events calendar: +5 new events (Chinese PMI, Fujairah,"
echo "     EU Gas Storage, Russian Production, Indian Imports)"
echo ""
echo "  📡 RSS feeds: 10 feeds with credibility weights (0.40–0.95)"
echo ""
echo "  🐦 Influencer list: 17 accounts with leading/lagging classification"
echo ""
echo "Next: run install_phase3b.sh"
echo "  → OilNewsScanner + RAG confidence decay + data provider upgrade"
echo "════════════════════════════════════════════════════"
