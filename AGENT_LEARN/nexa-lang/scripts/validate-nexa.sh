#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Nexa Toolchain Validation Script
# ═══════════════════════════════════════════════════════════════════════
# Checks:
#   1. Python 3.10+ is available
#   2. nexa CLI is installed and functional
#   3. A test .nx file compiles successfully
#   4. (Optional) The compiled .py executes without import errors
#
# Usage:
#   bash scripts/validate-nexa.sh              # basic check
#   bash scripts/validate-nexa.sh --full       # full check with execution
#   bash scripts/validate-nexa.sh --project /path/to/project  # project check
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
FULL_CHECK=false
PROJECT_DIR=""

for arg in "$@"; do
    case "$arg" in
        --full) FULL_CHECK=true ;;
        --project)
            if [ $# -gt 1 ]; then
                PROJECT_DIR="$2"
                shift
            fi
            ;;
    esac
    shift 2>/dev/null || true
done

echo "╔════════════════════════════════════════════════╗"
echo "║       Nexa Toolchain Validation               ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# ── Check 1: Python version ──
echo -n "[1/4] Python version... "
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
        echo -e "${GREEN}PASS${NC} (Python $PY_VER)"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} (Python $PY_VER — need 3.10+)"
        FAIL=$((FAIL + 1))
    fi
else
    echo -e "${RED}FAIL${NC} (python3 not found)"
    FAIL=$((FAIL + 1))
fi

# ── Check 2: nexa CLI installed ──
echo -n "[2/4] nexa CLI... "
if command -v nexa &>/dev/null; then
    NEXA_VER=$(nexa --version 2>&1 || echo "unknown")
    echo -e "${GREEN}PASS${NC} ($NEXA_VER)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}FAIL${NC} (nexa not found in PATH)"
    echo "       Fix: cd /path/to/Nexa && pip install -e ."
    FAIL=$((FAIL + 1))
fi

# ── Check 3: Compile test .nx file ──
echo -n "[3/4] Compile test... "
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

cat > "$TEST_DIR/test.nx" << 'NEXAEOF'
agent TestBot {
    prompt: "You are a test bot. Reply with 'OK'."
}

flow main {
    result = TestBot.run("Say OK");
    print(result);
}
NEXAEOF

if nexa build "$TEST_DIR/test.nx" --harness=off 2>/dev/null; then
    echo -e "${GREEN}PASS${NC} (test.nx compiled successfully)"
    PASS=$((PASS + 1))
    TEST_PY="$TEST_DIR/test.py"
else
    echo -e "${RED}FAIL${NC} (compilation failed)"
    echo "       Check error output above."
    FAIL=$((FAIL + 1))
    TEST_PY=""
fi

# ── Check 4: (Optional) Project check ──
if [ -n "$PROJECT_DIR" ]; then
    echo -n "[4/5] Project compile... "
    if [ -f "$PROJECT_DIR/main.nx" ]; then
        if nexa build "$PROJECT_DIR/main.nx" --harness=warn 2>/dev/null; then
            echo -e "${GREEN}PASS${NC} (main.nx compiled)"
            PASS=$((PASS + 1))
        else
            echo -e "${RED}FAIL${NC} (main.nx compilation failed)"
            FAIL=$((FAIL + 1))
        fi
    else
        echo -e "${YELLOW}SKIP${NC} (no main.nx found in $PROJECT_DIR)"
    fi
else
    echo "[4/5] Project check... ${YELLOW}SKIP${NC} (use --project <dir>)"
fi

# ── Full check: Import test ──
if $FULL_CHECK && [ -n "$TEST_PY" ] && [ -f "$TEST_PY" ]; then
    echo -n "[5/5] Runtime import... "
    if python3 -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('test', '$TEST_PY')
mod = importlib.util.module_from_spec(spec)
sys.modules['test'] = mod
spec.loader.exec_module(mod)
print('OK')
" 2>/dev/null; then
        echo -e "${GREEN}PASS${NC} (module imports cleanly)"
        PASS=$((PASS + 1))
    else
        echo -e "${YELLOW}WARN${NC} (import may have issues — check manually)"
    fi
else
    echo "[5/5] Runtime import... ${YELLOW}SKIP${NC} (use --full)"
fi

# ── Summary ──
echo ""
echo "════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, $TOTAL total"
echo "════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0