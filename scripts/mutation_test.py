#!/usr/bin/env python3
"""Hamilton ERP — Lightweight Mutation Testing Script

Applies simple mutations to lifecycle.py and locks.py one at a time,
runs the bench test suite after each, and reports which mutations
were caught (killed) vs survived.

Designed for Frappe/ERPNext where mutmut can't run due to Python 3.14
and bench-required test initialization.

Usage:
    python scripts/mutation_test.py
"""
import os
import re
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

# Derive paths from this script's location:
#   scripts/mutation_test.py → hamilton_erp/ (app root) → apps/ → bench dir
_SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = str(_SCRIPT_DIR.parent)                # apps/hamilton_erp
BENCH_DIR = str(_SCRIPT_DIR.parents[2])          # frappe-bench-hamilton
SITE = os.environ.get("HAMILTON_TEST_SITE", "hamilton-unit-test.localhost")
BENCH = shutil.which("bench") or "bench"

# Files to mutate
TARGETS = [
	"hamilton_erp/lifecycle.py",
	"hamilton_erp/locks.py",
]

# Test modules that exercise the target files
TEST_MODULES = [
	"hamilton_erp.test_lifecycle",
	"hamilton_erp.test_locks",
	"hamilton_erp.test_checklist_complete",
	"hamilton_erp.test_database_advanced",
]

# Mutations to apply (pattern, replacement, description)
MUTATIONS = [
	# State transitions
	(r'"Available"', '"Dirty"', "lifecycle.py: flip Available to Dirty in transition check"),
	(r'"Occupied"', '"Available"', "lifecycle.py: flip Occupied to Available in transition check"),
	(r'"Dirty"', '"Occupied"', "lifecycle.py: flip Dirty to Occupied in transition check"),
	# Comparison operators
	(r'== "Available"', '!= "Available"', "lifecycle.py: invert Available check"),
	(r'== "Occupied"', '!= "Occupied"', "lifecycle.py: invert Occupied check"),
	(r'== "Dirty"', '!= "Dirty"', "lifecycle.py: invert Dirty check"),
	(r'== "Out of Service"', '!= "Out of Service"', "lifecycle.py: invert OOS check"),
	# Version increment
	(r'version \+ 1', 'version + 2', "lifecycle.py: wrong version increment"),
	(r'version \+ 1', 'version', "lifecycle.py: skip version increment"),
	# Lock TTL
	(r'LOCK_TTL_MS\s*=\s*\d+', 'LOCK_TTL_MS = 1', "locks.py: reduce lock TTL to 1ms"),
	# Lock key namespace
	(r'hamilton:asset_lock:', 'wrong:namespace:', "locks.py: wrong Redis key namespace"),
	# Session number format
	(r'f"{seq:04d}"', 'f"{seq:02d}"', "lifecycle.py: wrong session number padding"),
	# Retry count
	(r'range\(3\)', 'range(0)', "lifecycle.py: zero retry attempts"),
	# Walkin customer
	(r'WALKIN_CUSTOMER\s*=\s*"Walk-in"', 'WALKIN_CUSTOMER = "Guest"', "lifecycle.py: wrong customer name"),
	# Vacate discovery
	(r'VACATE_DISCOVERY\s*=\s*"Discovery on Rounds"', 'VACATE_DISCOVERY = "Key Return"', "lifecycle.py: wrong vacate method"),
]


def run_tests():
	"""Run the test suite and return True if all pass."""
	cmds = []
	for mod in TEST_MODULES:
		cmds.append(f"{BENCH} --site {SITE} run-tests --app hamilton_erp --module {mod}")
	full_cmd = " && ".join(cmds)
	result = subprocess.run(
		full_cmd, shell=True, capture_output=True, text=True, timeout=300,
		cwd=BENCH_DIR,
	)
	return result.returncode == 0


def apply_mutation(filepath, pattern, replacement):
	"""Apply a mutation to a file. Returns True if the pattern was found."""
	full_path = os.path.join(APP_DIR, filepath)
	with open(full_path, "r") as f:
		original = f.read()

	mutated, count = re.subn(pattern, replacement, original, count=1)
	if count == 0:
		return False, original

	with open(full_path, "w") as f:
		f.write(mutated)
	return True, original


def restore_file(filepath, original):
	"""Restore a file to its original content."""
	full_path = os.path.join(APP_DIR, filepath)
	with open(full_path, "w") as f:
		f.write(original)


def main():
	killed = 0
	survived = 0
	skipped = 0
	survivors = []

	print(f"Hamilton ERP Mutation Testing")
	print(f"Targets: {', '.join(TARGETS)}")
	print(f"Mutations: {len(MUTATIONS)}")
	print(f"Test modules: {len(TEST_MODULES)}")
	print("=" * 60)

	# First verify baseline passes
	print("\n[BASELINE] Running tests without mutations...")
	if not run_tests():
		print("FATAL: Baseline tests fail! Fix tests before running mutation testing.")
		sys.exit(1)
	print("[BASELINE] PASSED\n")

	for i, (pattern, replacement, description) in enumerate(MUTATIONS, 1):
		# Determine which file to mutate
		if "locks.py" in description:
			filepath = "hamilton_erp/locks.py"
		else:
			filepath = "hamilton_erp/lifecycle.py"

		print(f"[{i}/{len(MUTATIONS)}] {description}")
		applied, original = apply_mutation(filepath, pattern, replacement)

		if not applied:
			print(f"  SKIPPED (pattern not found)")
			skipped += 1
			continue

		try:
			tests_pass = run_tests()
		except subprocess.TimeoutExpired:
			print(f"  TIMEOUT (killed — mutation caused infinite loop or hang)")
			killed += 1
			restore_file(filepath, original)
			continue

		restore_file(filepath, original)

		if tests_pass:
			print(f"  SURVIVED — tests did not catch this mutation!")
			survived += 1
			survivors.append(description)
		else:
			print(f"  KILLED")
			killed += 1

	print("\n" + "=" * 60)
	print(f"RESULTS: {killed} killed, {survived} survived, {skipped} skipped")
	total_applied = killed + survived
	if total_applied > 0:
		score = (killed / total_applied) * 100
		print(f"MUTATION SCORE: {score:.0f}% ({killed}/{total_applied})")
	else:
		print("No mutations were applied.")

	if survivors:
		print(f"\nSURVIVORS (tests missed these {len(survivors)} mutations):")
		for s in survivors:
			print(f"  - {s}")

	print()


if __name__ == "__main__":
	main()
