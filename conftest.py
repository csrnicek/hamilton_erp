"""Pytest conftest — boots Frappe so tests can run via pytest/mutmut.

bench run-tests does this automatically, but mutmut invokes pytest
directly and needs Frappe initialized before any test imports.

When mutmut runs, it copies this file into a `mutants/` subdirectory,
so all paths must be absolute.
"""
import os
import sys

# Ensure Frappe apps are importable regardless of working directory
BENCH_PATH = "/Users/chrissrnicek/frappe-bench-hamilton"
for app_path in [
	os.path.join(BENCH_PATH, "apps", "frappe"),
	os.path.join(BENCH_PATH, "apps", "erpnext"),
	os.path.join(BENCH_PATH, "apps", "hamilton_erp"),
]:
	if app_path not in sys.path:
		sys.path.insert(0, app_path)

import frappe

# Skip files that import from incompatible paths or need bench runner
collect_ignore_glob = [
	"hamilton_erp/hamilton_erp/*",
	"hamilton_erp/test_stress_simulation.py",
]


def pytest_configure(config):
	"""Initialize Frappe context once for the entire pytest session."""
	# Guard against double-init (mutmut may call configure multiple times)
	try:
		if frappe.local and frappe.local.site:
			return
	except Exception:
		pass

	site = "hamilton-unit-test.localhost"

	# Ensure cwd is the bench root so Frappe's logger finds its log dirs
	os.chdir(BENCH_PATH)

	frappe.init(
		site=site,
		sites_path=os.path.join(BENCH_PATH, "sites"),
	)
	frappe.connect()
	frappe.set_user("Administrator")


def pytest_unconfigure(config):
	"""Tear down Frappe context."""
	try:
		frappe.destroy()
	except Exception:
		pass
