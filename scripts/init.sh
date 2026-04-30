#!/usr/bin/env bash
# Hamilton ERP — fresh dev-bench bootstrap script.
#
# What this does:
#   - Verifies the version pins Frappe v16 requires (Python 3.14, Node 24,
#     yarn, MariaDB, redis-cli, frappe-bench, wkhtmltopdf).
#   - If any prerequisite is missing, prints the exact install command
#     and exits NON-ZERO. This script does NOT install system packages
#     for you — it tells you what's missing and where to get it.
#   - Once all prereqs pass, sets up a working bench at $BENCH_DIR with
#     frappe + erpnext + payments + hamilton_erp installed and a dev
#     site ($DEV_SITE) ready to use.
#   - Idempotent: re-running detects existing state and skips re-creation.
#
# What this does NOT do:
#   - Install Python via pyenv. Use `pyenv install 3.14.x` first.
#   - Install Node via nvm. Use `nvm install 24` first.
#   - Install MariaDB. Use `brew install mariadb` (macOS) or your
#     distro's mariadb-server package.
#   - Modify your shell profile.
#   - Touch production. This is local-bench setup only.
#
# Usage:
#   bash scripts/init.sh                  # uses defaults below
#   BENCH_DIR=~/my-bench bash scripts/init.sh
#
# Source for the install steps: .github/workflows/tests.yml. The CI
# workflow is the authoritative install path; this script is its
# local-bench mirror. Major divergences from CI are commented inline.
#
# Reference:
#   docs/lessons_learned.md (LL-001, LL-006, LL-025, LL-027)
#   CLAUDE.md "Technical environment"
#   docs/RUNBOOK.md §5 (infrastructure health)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — override via env vars
# ---------------------------------------------------------------------------

BENCH_DIR="${BENCH_DIR:-${HOME}/frappe-bench-hamilton}"
DEV_SITE="${DEV_SITE:-hamilton-test.localhost}"
TEST_SITE="${TEST_SITE:-hamilton-unit-test.localhost}"
APP_DIR="${APP_DIR:-${HOME}/hamilton_erp}"

# Version pins — match Frappe v16's hard requirements per CLAUDE.md
REQUIRED_PYTHON_MAJOR_MINOR="3.14"
REQUIRED_NODE_MAJOR="24"

# Frappe v16 branch refs (match the CI workflow tests.yml)
FRAPPE_REF="version-16"
ERPNEXT_REF="version-16"
PAYMENTS_REF="develop"   # frappe/payments has not cut a v16 branch yet (per LL / inbox 2026-04-28)

# MariaDB credentials (match CLAUDE.md). Local-bench only — never use these in production.
MARIADB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Colored output without requiring tput on every system. Tested on macOS Terminal + iTerm2.
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
CYAN=$'\033[0;36m'
RESET=$'\033[0m'

log_step()  { printf "\n%s▶ %s%s\n" "$CYAN" "$1" "$RESET"; }
log_ok()    { printf "%s  ✓ %s%s\n" "$GREEN" "$1" "$RESET"; }
log_warn()  { printf "%s  ⚠ %s%s\n" "$YELLOW" "$1" "$RESET"; }
log_fail()  { printf "%s  ✗ %s%s\n" "$RED" "$1" "$RESET"; }

die() {
	log_fail "$1"
	echo "" >&2
	echo "Aborting init.sh. Fix the above issue and re-run." >&2
	exit 1
}

# Compare semver-ish "major.minor" strings. Returns 0 if $1 >= $2.
version_at_least() {
	local actual="$1" required="$2"
	[ "$(printf '%s\n' "$required" "$actual" | sort -V | head -1)" = "$required" ]
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

check_python() {
	log_step "Python ${REQUIRED_PYTHON_MAJOR_MINOR}"
	if ! command -v python3 >/dev/null 2>&1; then
		die "python3 not found. Install via: pyenv install ${REQUIRED_PYTHON_MAJOR_MINOR}.0 && pyenv shell ${REQUIRED_PYTHON_MAJOR_MINOR}.0"
	fi
	local actual
	actual=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
	if [ "$actual" != "$REQUIRED_PYTHON_MAJOR_MINOR" ]; then
		die "Python ${actual} is active; Frappe v16 requires ${REQUIRED_PYTHON_MAJOR_MINOR}. Run: pyenv shell ${REQUIRED_PYTHON_MAJOR_MINOR}.0  (Frappe 16.16.0's pyproject.toml pins >=3.14,<3.15. 3.13 fails with depends-on error; 3.11 fails earlier on PEP 695 syntax.)"
	fi
	log_ok "python3 = $(python3 --version) ($(command -v python3))"
}

check_node() {
	log_step "Node ${REQUIRED_NODE_MAJOR}"
	if ! command -v node >/dev/null 2>&1; then
		die "node not found. Install via: nvm install ${REQUIRED_NODE_MAJOR} && nvm use ${REQUIRED_NODE_MAJOR}"
	fi
	local actual
	actual=$(node --version | sed 's/^v//' | cut -d. -f1)
	if [ "$actual" != "$REQUIRED_NODE_MAJOR" ]; then
		die "Node ${actual} is active; Frappe v16 requires Node ${REQUIRED_NODE_MAJOR}. Run: nvm use ${REQUIRED_NODE_MAJOR}  (Frappe's package.json declares engines.node >= 24. Node 20 fails 'yarn install --check-files' with engine incompatibility.)"
	fi
	log_ok "node = $(node --version) ($(command -v node))"
}

check_yarn() {
	log_step "yarn"
	if ! command -v yarn >/dev/null 2>&1; then
		die "yarn not found. Install via: npm install -g yarn"
	fi
	log_ok "yarn = $(yarn --version)"
}

check_mariadb() {
	log_step "MariaDB"
	if ! command -v mariadb >/dev/null 2>&1 && ! command -v mysql >/dev/null 2>&1; then
		die "MariaDB client not found. macOS: brew install mariadb. Linux: install mariadb-client + mariadb-server."
	fi
	# We don't pin a MariaDB version here — Frappe v16 supports 11.4+. CLAUDE.md
	# documents 12.2.2 in use; CI uses 11.8. Match whichever is installed.
	if command -v mariadb >/dev/null 2>&1; then
		log_ok "mariadb client = $(mariadb --version)"
	else
		log_warn "mariadb client not found, falling back to mysql"
		log_ok "mysql client = $(mysql --version)"
	fi

	# Connectivity check
	if ! mariadb -uroot -p"${MARIADB_ROOT_PASSWORD}" -e 'SELECT 1' >/dev/null 2>&1 \
	   && ! mysql -uroot -p"${MARIADB_ROOT_PASSWORD}" -e 'SELECT 1' >/dev/null 2>&1; then
		die "Cannot connect to MariaDB as root with MARIADB_ROOT_PASSWORD='${MARIADB_ROOT_PASSWORD}'. Either start MariaDB (brew services start mariadb), or set MARIADB_ROOT_PASSWORD to your actual root password."
	fi
	log_ok "MariaDB reachable on socket/localhost as root"
}

check_redis() {
	log_step "redis-cli"
	if ! command -v redis-cli >/dev/null 2>&1; then
		die "redis-cli not found. macOS: brew install redis. Linux: install redis-server."
	fi
	log_ok "redis-cli = $(redis-cli --version)"
	# Note: bench runs its own Redis on ports 13000 (cache) and 11000 (queue).
	# We don't check those here — `bench start` brings them up via Procfile.
	# Per LL-025, the system Redis on 6379 is NOT used by bench. Conflicts
	# possible if you run `redis-server` standalone on the default port; safe
	# to leave system Redis stopped while bench is active.
}

check_wkhtmltopdf() {
	log_step "wkhtmltopdf (PDF print formats)"
	if ! command -v wkhtmltopdf >/dev/null 2>&1; then
		log_warn "wkhtmltopdf not found. PDF print formats will not render."
		log_warn "  macOS: brew install wkhtmltopdf"
		log_warn "  Linux: apt install wkhtmltopdf  (or download from https://wkhtmltopdf.org)"
		log_warn "Continuing anyway — wkhtmltopdf is non-blocking for app install."
	else
		log_ok "wkhtmltopdf = $(wkhtmltopdf --version 2>&1 | head -1)"
	fi
}

check_frappe_bench() {
	log_step "frappe-bench"
	if ! command -v bench >/dev/null 2>&1; then
		die "bench not found. Install via: pip install frappe-bench"
	fi
	log_ok "bench = $(bench --version 2>&1 | head -1)"
}

check_app_dir() {
	log_step "Hamilton ERP app source"
	if [ ! -d "$APP_DIR" ]; then
		die "Hamilton ERP source not found at ${APP_DIR}. Clone via: git clone https://github.com/csrnicek/hamilton_erp.git ${APP_DIR}"
	fi
	if [ ! -f "${APP_DIR}/hamilton_erp/hooks.py" ]; then
		die "${APP_DIR} exists but doesn't look like the hamilton_erp repo (missing hamilton_erp/hooks.py)."
	fi
	log_ok "hamilton_erp source at ${APP_DIR}"
}

# ---------------------------------------------------------------------------
# Bench bootstrap
# ---------------------------------------------------------------------------

init_bench() {
	log_step "Initialize bench at ${BENCH_DIR}"
	if [ -d "${BENCH_DIR}/apps/frappe" ]; then
		log_ok "Bench already exists at ${BENCH_DIR}; skipping bench init"
		return 0
	fi

	bench init "${BENCH_DIR}" \
		--frappe-branch "${FRAPPE_REF}" \
		--python "$(command -v python3)" \
		--ignore-exist \
		--no-backups
	log_ok "Bench initialized"
}

get_apps() {
	log_step "Fetch ERPNext + Payments + hamilton_erp into bench/apps"
	cd "${BENCH_DIR}"

	if [ ! -d "apps/erpnext" ]; then
		bench get-app erpnext --branch "${ERPNEXT_REF}"
		log_ok "Fetched erpnext (${ERPNEXT_REF})"
	else
		log_ok "erpnext already present in bench"
	fi

	if [ ! -d "apps/payments" ]; then
		# frappe/payments has no v16 branch as of 2026-04-28 — use develop.
		# Required because Frappe's IntegrationTestCase.setUpClass walks
		# Link fields recursively and chains end at Payment Gateway.
		# See docs/inbox.md 2026-04-28 entry, docs/RUNBOOK.md §6.1.
		bench get-app https://github.com/frappe/payments --branch "${PAYMENTS_REF}"
		log_ok "Fetched payments (${PAYMENTS_REF})"
	else
		log_ok "payments already present in bench"
	fi

	if [ ! -d "apps/hamilton_erp" ]; then
		bench get-app hamilton_erp "${APP_DIR}"
		log_ok "Linked hamilton_erp from ${APP_DIR}"
	else
		log_ok "hamilton_erp already present in bench"
	fi

	# Test extras (hypothesis) — declared in pyproject.toml [test] extra.
	# `bench get-app` already pip-installed the main package; this re-installs
	# with the [test] extra so hypothesis lands in the bench env.
	"${BENCH_DIR}/env/bin/pip" install -e "${BENCH_DIR}/apps/hamilton_erp[test]" >/dev/null
	log_ok "Installed hamilton_erp[test] extras (hypothesis)"
}

configure_bench() {
	log_step "Configure bench credentials"
	cd "${BENCH_DIR}"
	bench set-config -g root_login root
	bench set-config -g root_password "${MARIADB_ROOT_PASSWORD}"
	bench set-config -g admin_password "${ADMIN_PASSWORD}"
	log_ok "Set root_login, root_password, admin_password"
}

create_site() {
	local site_name="$1"
	log_step "Create site ${site_name}"
	cd "${BENCH_DIR}"

	if bench --site "${site_name}" list-apps >/dev/null 2>&1; then
		log_ok "Site ${site_name} already exists; skipping bench new-site"
		return 0
	fi

	bench new-site "${site_name}" \
		--db-type mariadb \
		--db-host 127.0.0.1 \
		--db-port 3306 \
		--mariadb-root-password "${MARIADB_ROOT_PASSWORD}" \
		--admin-password "${ADMIN_PASSWORD}" \
		--no-mariadb-socket \
		--install-app erpnext \
		--install-app payments \
		--install-app hamilton_erp

	log_ok "Site ${site_name} created with erpnext + payments + hamilton_erp installed"
}

configure_test_site() {
	local site_name="$1"
	log_step "Configure ${site_name} for testing"
	cd "${BENCH_DIR}"

	bench --site "${site_name}" set-config allow_tests 1 --parse
	bench --site "${site_name}" set-config server_script_enabled 1 --parse
	log_ok "${site_name}: allow_tests=1, server_script_enabled=1"
}

run_migrate() {
	local site_name="$1"
	log_step "Run bench migrate on ${site_name} (fires after_migrate hook)"
	cd "${BENCH_DIR}"
	bench --site "${site_name}" migrate
	log_ok "${site_name} migrated"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
	echo ""
	echo "Hamilton ERP — fresh-bench bootstrap"
	echo "------------------------------------"
	echo "BENCH_DIR  = ${BENCH_DIR}"
	echo "DEV_SITE   = ${DEV_SITE}   (browser dev site — never run tests against this)"
	echo "TEST_SITE  = ${TEST_SITE}  (unit-test site — wipe-able)"
	echo "APP_DIR    = ${APP_DIR}"
	echo ""

	# Step 1 — verify prereqs (bail early with actionable error messages)
	check_python
	check_node
	check_yarn
	check_mariadb
	check_redis
	check_wkhtmltopdf
	check_frappe_bench
	check_app_dir

	# Step 2 — bench
	init_bench
	get_apps
	configure_bench

	# Step 3 — sites (dev + test)
	create_site "${DEV_SITE}"
	# Dev site: NO allow_tests flag — running tests against it corrupts state.
	# (CLAUDE.md "Technical environment" — the dev-site warning).

	create_site "${TEST_SITE}"
	configure_test_site "${TEST_SITE}"

	# Step 4 — apply patches (after_migrate hook fires for is_setup_complete heal)
	run_migrate "${DEV_SITE}"
	run_migrate "${TEST_SITE}"

	# Done
	echo ""
	log_step "Done."
	cat <<EOF

Next steps:

  1) Start the bench:
       cd ${BENCH_DIR} && bench start

  2) Open the dev site in a browser:
       http://${DEV_SITE}:8000
     Log in as Administrator / ${ADMIN_PASSWORD}.

  3) Run the test suite (NEVER against the dev site):
       cd ${BENCH_DIR} && source env/bin/activate
       bench --site ${TEST_SITE} run-tests --app hamilton_erp

  4) Read these next:
       - docs/RUNBOOK.md            (operational incident response)
       - docs/decisions_log.md      (LOCKED design decisions)
       - docs/lessons_learned.md    (recurring-failure catalogue)
       - CLAUDE.md                  (project conventions)

  Bench data:
       Dev site DB:    ${DEV_SITE}
       Test site DB:   ${TEST_SITE}
       MariaDB root:   ${MARIADB_ROOT_PASSWORD}  (local-bench only)
       Admin password: ${ADMIN_PASSWORD}         (local-bench only)
EOF
}

main "$@"
