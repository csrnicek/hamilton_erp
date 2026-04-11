"""Post-test restore hook for Hamilton ERP.

Every test module calls ``restore_dev_state()`` in its ``tearDownModule``
function. Why: tests and dev share a single site (hamilton-test.localhost)
because no separate test site is configured. Test teardowns wipe data,
defaults, and User roles, which leaves the dev browser broken between
test runs in three specific ways:

1. ``setup_complete`` default flips back to 0 → infinite setup_wizard
   loop on the next browser request.
2. The ``Hamilton Operator`` role gets stripped from Administrator →
   Asset Board returns "Not permitted".
3. All 59 Venue Assets get deleted → Asset Board renders an empty grid.

This helper restores all three. It is idempotent, safe to call multiple
times, and intentionally does NOT touch anything a test might legitimately
care about (Venue Sessions, Asset Status Logs, etc. are left alone — tests
wipe those in their own setUp).

Long-term fix: configure a separate test site so tests can freely wipe
without touching dev state. This module is the interim fix.
"""
import frappe


def restore_dev_state():
	"""Restore the three pieces of dev state that test runs destroy.

	Called from ``tearDownModule`` in every test file listed in the
	``/run-tests`` slash command. Idempotent.
	"""
	# 1. setup_complete — unblocks the browser from the setup_wizard loop.
	#    Frappe reads ``frappe.db.get_default("setup_complete")`` at boot,
	#    NOT the System Settings singleton, so both must be set.
	frappe.db.set_default("setup_complete", "1")
	frappe.db.set_single_value("System Settings", "setup_complete", 1)

	# 2. Hamilton Operator role on Administrator — required for the
	#    Asset Board page and the ``get_asset_board_data`` API call.
	#    Only add if the role exists (avoids test failures on a fresh
	#    site where the role fixture hasn't been installed yet).
	if frappe.db.exists("Role", "Hamilton Operator"):
		admin = frappe.get_doc("User", "Administrator")
		existing_roles = {r.role for r in admin.roles}
		if "Hamilton Operator" not in existing_roles:
			admin.append("roles", {"role": "Hamilton Operator"})
			admin.save(ignore_permissions=True)

	# 3. Re-seed the 59 venue assets + Walk-in + Hamilton Settings.
	#    seed_hamilton_env.execute() is idempotent per DEC-054 so this
	#    is safe even if a test left partial state behind.
	from hamilton_erp.patches.v0_1 import seed_hamilton_env
	seed_hamilton_env.execute()

	frappe.db.commit()

	# 4. Flush Redis so the next browser request doesn't hit stale
	#    role/default caches. clear_cache() is a no-op if Redis is
	#    unreachable (e.g., during a crashed test run).
	try:
		frappe.clear_cache()
	except Exception:
		pass
