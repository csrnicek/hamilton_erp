"""Three-layer lock helper for Venue Asset status changes.

Usage:
    with asset_status_lock(asset_name, "assign") as row:
        # row is {"name", "status", "version"} read under FOR UPDATE
        # ... mutate, save, create log — NO I/O here ...
    # ... publish_realtime, enqueue, print — out here, after the with-block

Layer 1: Redis advisory lock with UUID token (atomic NX set, Lua release)
Layer 2: MariaDB row lock via SELECT … FOR UPDATE
Layer 3: Version-field check — caller's responsibility, compares row["version"]
         to the document's version before saving
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _

LOCK_TTL_MS = 15_000  # 15s — every critical section must complete well under this

# Lua CAS release script: atomically delete the Redis lock key only if the
# stored token still matches ours. Prevents a slow caller from unlocking a
# key another caller acquired after its TTL expired.
_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class LockContentionError(frappe.ValidationError):
	"""Raised when the Redis advisory lock cannot be acquired."""


@contextmanager
def asset_status_lock(asset_name: str, operation: str) -> Iterator[dict]:
	"""Acquire the three-layer lock for a Venue Asset status change.

	Yields: {"name", "status", "version"} — the row read under FOR UPDATE.
	Raises: LockContentionError if the Redis lock is held by another caller.
	"""
	cache = frappe.cache()
	key = f"hamilton:asset_lock:{asset_name}:{operation}"
	token = uuid.uuid4().hex
	# Layer 1 — Redis NX set with TTL
	acquired = cache.set(key, token, nx=True, px=LOCK_TTL_MS)
	if not acquired:
		raise LockContentionError(
			_(
				"Asset {0} is being processed by another operator. "
				"Refresh the board and try again."
			).format(asset_name)
		)
	try:
		# Layer 2 — MariaDB row lock
		rows = frappe.db.sql(
			"SELECT name, status, version FROM `tabVenue Asset` "
			"WHERE name = %s FOR UPDATE",
			asset_name,
			as_dict=True,
		)
		if not rows:
			frappe.throw(_("Venue Asset {0} not found.").format(asset_name))
		yield rows[0]
	finally:
		# Atomic release via Lua CAS — only delete if the token is still ours.
		# This is Redis server-side Lua scripting (EVAL command), not Python eval.
		try:
			cache.eval(_RELEASE_SCRIPT, 1, key, token)
		except Exception:
			# Lock will TTL out — log but don't mask the primary exception
			frappe.logger().warning(
				f"asset_status_lock: Lua release failed for {key}; TTL fallback"
			)
