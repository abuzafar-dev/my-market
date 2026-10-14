#!/usr/bin/env bash
# Backend checks for the local ci-gate pre-push hook.
#
# It mirrors the backend job of .github/workflows/ci.yml (ruff, migrations
# check, tests) but is not called by it; the frontend job (npm lint/build)
# runs only in GitHub Actions. It stops at the first failing check and exits
# non-zero.
#
#   scripts/ci.sh            # every check
#   scripts/ci.sh backend    # Python checks only
#   scripts/ci.sh frontend   # frontend checks only (when FRONTEND_DIR is set)
#
# Dependencies go into a private virtualenv (.venv-ci, or $CI_GATE_VENV), never
# into the system Python. uv is used when available, plain venv + pip otherwise.
set -euo pipefail
cd "$(dirname "$0")/.."

# --- per-repository settings -------------------------------------------------
PYTHON_VERSION="3.14"
PROJECT_DIR="."                    # where manage.py / pyproject.toml live
REQUIREMENTS="requirements-dev.txt" # pip mode; includes requirements.txt + ruff
TEST_CMD="ruff check . && ruff format --check . && python manage.py test --parallel 4"  # same as .github/workflows/ci.yml
FRONTEND_DIR=""                    # e.g. "frontend" to also run npm ci / lint / build
# Placeholder settings so the project imports without a real .env.
# Tests never need production credentials.
export SECRET_KEY="${SECRET_KEY:-ci-only-insecure-key-not-a-secret}"
export DEBUG="${DEBUG:-False}"
# Same placeholders as .github/workflows/ci.yml: config.settings.test swaps in
# an in-memory SQLite DB, so DATABASE_URL is never connected to.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.test}"
export DATABASE_URL="${DATABASE_URL:-postgresql://user:pass@localhost:5432/db}"  # pragma: allowlist secret
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost}"
# -----------------------------------------------------------------------------

part="${1:-all}"
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

python_env() {
    local venv="${CI_GATE_VENV:-$PWD/.venv-ci}"
    if [ ! -x "$venv/bin/python" ]; then
        step "creating virtualenv ($venv, Python $PYTHON_VERSION)"
        if command -v uv >/dev/null 2>&1; then
            uv venv --quiet --python "$PYTHON_VERSION" "$venv"
        else
            "python$PYTHON_VERSION" -m venv "$venv"
        fi
    fi
    export VIRTUAL_ENV="$venv" PATH="$venv/bin:$PATH"

    local lock="$PROJECT_DIR/uv.lock" hash stamp="$venv/.ci-deps"
    if [ -f "$lock" ]; then
        hash=$(cat "$PROJECT_DIR/pyproject.toml" "$lock" | sha256sum | cut -c1-16)
    else
        hash=$( (cd "$PROJECT_DIR" && cat $REQUIREMENTS) | sha256sum | cut -c1-16)
    fi
    [ "$(cat "$stamp" 2>/dev/null)" = "$hash" ] && return 0

    step "installing Python dependencies"
    if [ -f "$lock" ]; then
        (cd "$PROJECT_DIR" && UV_PROJECT_ENVIRONMENT="$venv" uv sync --quiet --frozen)
    else
        local args=() r
        for r in $REQUIREMENTS; do args+=(-r "$r"); done
        if command -v uv >/dev/null 2>&1; then
            (cd "$PROJECT_DIR" && uv pip install --quiet "${args[@]}")
        else
            (cd "$PROJECT_DIR" && python -m pip install --quiet "${args[@]}")
        fi
    fi
    echo "$hash" > "$stamp"
}

# Fails when the runner reports zero tests: an empty suite is not a pass.
require_tests_ran() {
    if ! grep -Eq '(^Ran [1-9][0-9]* tests?)|([1-9][0-9]* passed)' "$1"; then
        echo "ERROR: no tests ran. Add real tests before pushing." >&2
        return 1
    fi
}

backend() {
    python_env
    local log
    log=$(mktemp)
    trap 'rm -f "$log"' RETURN
    (
        cd "$PROJECT_DIR"
        if [ -f manage.py ]; then
            step "Django system check"
            python manage.py check
            step "migrations match the models"
            python manage.py makemigrations --check --dry-run
        fi
        step "tests"
        if [ -n "$TEST_CMD" ]; then
            eval "$TEST_CMD"
        elif [ -f manage.py ]; then
            python manage.py test
        else
            python -m pytest
        fi
    ) 2>&1 | tee "$log"
    require_tests_ran "$log"
}

frontend() {
    [ -n "$FRONTEND_DIR" ] || return 0
    (
        cd "$FRONTEND_DIR"
        step "frontend: npm ci"
        npm ci --no-audit --no-fund
        if npm run | grep -q '^  lint$'; then
            step "frontend: lint"
            npm run lint
        fi
        if npm run | grep -q '^  test$'; then
            step "frontend: test"
            npm test
        fi
        step "frontend: build"
        npm run build
    )
}

case "$part" in
    all) backend; frontend ;;
    backend) backend ;;
    frontend) frontend ;;
    *) echo "usage: scripts/ci.sh [all|backend|frontend]" >&2; exit 2 ;;
esac
step "all checks passed"
