"""Venue Asset state-transition and session lifecycle core.

Public API (called from venue_asset.py whitelisted methods and from api.py):
    start_session_for_asset, vacate_session, mark_asset_clean,
    set_asset_out_of_service, return_asset_to_service, mark_all_clean

All public functions:
  - acquire the three-layer lock (locks.asset_status_lock)
  - validate the transition
  - mutate the asset, bump version, write timestamps
  - create an Asset Status Log entry (skipped in tests — see _make_asset_status_log)
  - publish the realtime event OUTSIDE the lock (via hamilton_erp.realtime)

No function here performs I/O (print, enqueue, publish_realtime) inside
the lock section.
"""
from __future__ import annotations

from typing import Optional

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# State machine — single source of truth
# ---------------------------------------------------------------------------
#
# This is the canonical state map for Venue Asset status transitions.
# The VenueAsset controller (venue_asset.py) imports this constant for its
# validate() hook, so the map is defined ONCE here. Do not duplicate.

VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
	"Available": ("Occupied", "Out of Service"),
	"Occupied": ("Dirty", "Out of Service"),
	"Dirty": ("Available", "Out of Service"),
	"Out of Service": ("Available",),
}


def _require_transition(row: dict, *, current: str, target: str, asset_name: str) -> None:
	"""Throw if row["status"] != current OR if current→target is not a valid edge."""
	if row["status"] != current:
		frappe.throw(_("Cannot {0} {1}: current status is {2}, expected {3}.")
		             .format(target.lower(), asset_name, row["status"], current))
	if target not in VALID_TRANSITIONS.get(current, ()):
		frappe.throw(_("Invalid transition {0}→{1} for {2}.")
		             .format(current, target, asset_name))


def _require_oos_entry(row: dict, *, asset_name: str) -> None:
	"""Out of Service can come from Available / Occupied / Dirty, but not from itself."""
	if row["status"] == "Out of Service":
		frappe.throw(_("Asset {0} is already Out of Service.").format(asset_name))


# ---------------------------------------------------------------------------
# Asset Status Log — in-test guard (Grok review 2026-04-10)
# ---------------------------------------------------------------------------


def _make_asset_status_log(
	*,
	asset_name: str,
	previous: str,
	new_status: str,
	reason: Optional[str],
	operator: str,
	venue_session: Optional[str],
) -> Optional[str]:
	"""Create an Asset Status Log entry. Short-circuits in tests.

	Returns the log name, or None when suppressed.

	Tests that specifically assert log creation must clear frappe.flags.in_test
	locally via setUp/tearDown.
	"""
	if frappe.flags.in_test:
		return None
	log = frappe.get_doc({
		"doctype": "Asset Status Log",
		"venue_asset": asset_name,
		"previous_status": previous,
		"new_status": new_status,
		"reason": reason,
		"operator": operator,
		"venue_session": venue_session,
		"timestamp": frappe.utils.now_datetime(),
	}).insert(ignore_permissions=True)
	return log.name


# ---------------------------------------------------------------------------
# Public lifecycle functions
# ---------------------------------------------------------------------------


def start_session_for_asset(asset_name: str, *, operator: str, customer: str = "Walk-in") -> str:
	"""Available → Occupied + create Venue Session. Returns session name."""
	from hamilton_erp.locks import asset_status_lock
	from hamilton_erp.realtime import publish_status_change

	with asset_status_lock(asset_name, "assign") as row:
		_require_transition(row, current="Available", target="Occupied",
		                    asset_name=asset_name)
		# NOTE: _create_session runs BEFORE _set_asset_status. A throw from
		# _set_asset_status (e.g. hypothetical version-CAS failure) would leave
		# the Venue Session insert pending — the request-level transaction rolls
		# it back in a normal HTTP call path. Programmatic callers MUST NOT
		# wrap this in try/except; let exceptions propagate to trigger rollback.
		session_name = _create_session(asset_name, operator=operator, customer=customer)
		_set_asset_status(
			asset_name,
			new_status="Occupied",
			session=session_name,
			log_reason=None,
			operator=operator,
			previous="Available",
			expected_version=row["version"],
		)
	publish_status_change(asset_name, previous_status="Available")
	return session_name


# ---------------------------------------------------------------------------
# Private helpers (all run INSIDE the lock — zero I/O except the permitted writes)
# ---------------------------------------------------------------------------


def _create_session(asset_name: str, *, operator: str, customer: str) -> str:
	"""Insert a Venue Session row for a freshly-assigned asset. Caller holds the asset lock.

	NOTE: session_number is NOT set here — VenueSession.before_insert
	auto-populates it via lifecycle._next_session_number(). identity_method
	defaults to 'not_applicable' via the controller's _set_defaults hook.

	Retry contract (Task 11(c)): the DB has a UNIQUE constraint on
	`session_number`. If a Redis hiccup or cold-start race ever produces a
	duplicate, the INSERT raises UniqueValidationError (field-level unique
	violation, raised by frappe.model.base_document.show_unique_validation_message).
	We catch it, retry up to 3 times, rebuilding a fresh doc dict each
	attempt so `before_insert` re-runs and calls `_next_session_number()`
	again — which hits Redis INCR and yields a fresh value. On the 3rd
	failure we raise ValidationError with a user-friendly message. The
	warning log is acceptable inside the lock body (stdlib logging, no
	network I/O).

	Exception-handling scope (Task 11 code review, I3): only
	frappe.UniqueValidationError is caught — it is the sole real trigger
	here because `venue_session.json` uses `"autoname": "hash"`, and
	frappe.model.base_document._handle_hash_conflict retries `name` hash
	collisions INTERNALLY. DuplicateEntryError was considered and rejected:
	it cannot reach this call site under `autoname: hash`, so catching it
	would be speculative error handling per coding_standards.md. Do not
	re-add it without first changing autoname away from hash.

	msgprint hygiene (Task 11 code review, I1): Frappe's
	base_document.show_unique_validation_message appends a
	`_("{0} must be unique")` toast to `frappe.local.message_log` BEFORE
	raising UniqueValidationError. Without intervention, a successful
	retry would still ship that stale toast to the client alongside the
	success response — the operator would see a confusing
	"Session Number must be unique" warning for an assignment that
	actually succeeded. We snapshot `message_log` at the top of each
	iteration and restore it on the caught exception so the failed
	attempt's toast is discarded.
	"""
	for attempt in range(1, 4):
		msg_log_snapshot = list(getattr(frappe.local, "message_log", []) or [])
		try:
			session = frappe.get_doc({
				"doctype": "Venue Session",
				"venue_asset": asset_name,
				"operator_checkin": operator,
				"customer": customer,
				"session_start": frappe.utils.now_datetime(),
				"status": "Active",
				"assignment_status": "Assigned",
			}).insert(ignore_permissions=True)
			return session.name
		except frappe.UniqueValidationError as exc:
			# Scope tightly (Task 11 3-AI review, Fix 8): only retry when the
			# collision is on `session_number`. If a future migration adds
			# another unique field (or a caller violates a different
			# constraint), silently retrying 3 times would mask the real
			# error. Re-raise without touching message_log so the real toast
			# reaches the client.
			if "session_number" not in str(exc):
				raise
			# Discard the "must be unique" toast left by the failed attempt —
			# otherwise a successful retry ships it to the client alongside
			# the success response (operators would see a confusing toast
			# for an assignment that actually succeeded).
			frappe.local.message_log = msg_log_snapshot
			frappe.logger().warning(
				f"_create_session: collision on attempt {attempt} for asset "
				f"{asset_name} — retrying with fresh session_number."
			)
			continue
	# All 3 attempts exhausted — surface a user-friendly message. `from None`
	# so the retry wrapper's message is not buried by the underlying
	# UniqueValidationError's args tuple.
	raise frappe.ValidationError(
		_("Session number collision — please try again.")
	) from None


def _set_asset_status(
	asset_name: str,
	*,
	new_status: str,
	session: Optional[str],
	log_reason: Optional[str],
	operator: str,
	previous: str,
	expected_version: int,
	log_venue_session: Optional[str] = None,
) -> None:
	"""Write the new status, bump version, and create the audit log.

	The caller must have just read `expected_version` under FOR UPDATE inside the
	same lock, so an optimistic-lock conflict here would be a bug, not a race.

	`session` is written to `asset.current_session` (None clears it, e.g. on vacate).
	`log_venue_session` is the FK written into the Asset Status Log row. When
	omitted it defaults to `session` — which is correct for start_session (the
	asset's new current_session IS the session to log). On vacate, the caller
	passes `session=None` (to clear current_session) but `log_venue_session=
	<closed session name>` so the audit row still links to the session that
	was closed. Task 4's start_session callers rely on the default.
	"""
	if log_venue_session is None:
		log_venue_session = session
	# for_update=True bypasses frappe.local.document_cache, which could return
	# a pre-lock snapshot if an earlier get_doc in this request cached the asset.
	# Safe — we already hold the row lock via the caller's asset_status_lock.
	asset = frappe.get_doc("Venue Asset", asset_name, for_update=True)
	if asset.version != expected_version:
		frappe.throw(_("Concurrent update to {0} — please refresh and retry.")
		             .format(asset_name))
	asset.status = new_status
	asset.current_session = session
	asset.version = expected_version + 1
	asset.hamilton_last_status_change = frappe.utils.now_datetime()
	if new_status == "Out of Service":
		asset.reason = log_reason
	else:
		# Gemini AI review 2026-04-10, generalized by 3-AI review 2026-04-10:
		# the `reason` field is OOS-specific. ANY transition that does not
		# enter OOS clears it, so a stale reason can never linger on an
		# asset whose status no longer justifies one. The load-bearing case
		# is OOS → Available (via return_asset_to_service) — without this,
		# an asset that was once OOS would carry the reason forever. The
		# generalization to plain `else` is defense-in-depth: even if some
		# future code path wrote a reason on a non-OOS asset, the next
		# legitimate transition would scrub it. Note: the audit log row
		# below still records `log_reason` (e.g. the return/repair reason);
		# we only null out the persisted reason on the asset row itself.
		asset.reason = None
	asset.save(ignore_permissions=True)
	_make_asset_status_log(
		asset_name=asset_name,
		previous=previous,
		new_status=new_status,
		reason=log_reason,
		operator=operator,
		venue_session=log_venue_session,
	)


# ---------------------------------------------------------------------------
# Vacate (Occupied → Dirty) — Task 5
# ---------------------------------------------------------------------------

# SOURCE OF TRUTH: venue_session.json `vacate_method` Select field options.
# Keep in sync — any change to the Select list here MUST also update the doctype JSON.
_VACATE_METHODS = ("Key Return", "Discovery on Rounds")


def vacate_session(asset_name: str, *, operator: str, vacate_method: str) -> None:
	"""Occupied → Dirty + close linked Venue Session."""
	# Validate operator input BEFORE acquiring the lock. `assert` would be
	# stripped by `python -O`, so use frappe.throw to raise ValidationError
	# which is safe in all run modes.
	if vacate_method not in _VACATE_METHODS:
		frappe.throw(
			_("Invalid vacate method {0}. Must be one of: {1}.").format(
				vacate_method, ", ".join(_VACATE_METHODS)
			)
		)
	from hamilton_erp.locks import asset_status_lock
	from hamilton_erp.realtime import publish_status_change

	with asset_status_lock(asset_name, "vacate") as row:
		_require_transition(row, current="Occupied", target="Dirty",
		                    asset_name=asset_name)
		# NOTE: _close_current_session runs BEFORE _set_asset_status. A throw
		# from _set_asset_status (e.g. hypothetical version-CAS failure) would
		# leave the Venue Session already marked Completed — the request-level
		# transaction rolls it back in a normal HTTP call path. Programmatic
		# callers MUST NOT wrap this in try/except; let exceptions propagate
		# to trigger rollback. Matches the Task 4 start_session_for_asset pattern.
		#
		# The lock row dict already includes `current_session` (see locks.py
		# SELECT list) — read it here so we don't issue a redundant DB read
		# inside _close_current_session.
		current_session = row["current_session"]
		_close_current_session(
			asset_name,
			current_session=current_session,
			operator=operator,
			vacate_method=vacate_method,
		)
		_set_asset_status(
			asset_name,
			new_status="Dirty",
			session=None,                      # clears asset.current_session
			log_venue_session=current_session, # but the log row still links to the closed session
			log_reason=None,
			operator=operator,
			previous="Occupied",
			expected_version=row["version"],
		)
		_set_vacated_timestamp(asset_name)
	publish_status_change(asset_name, previous_status="Occupied")


def _close_current_session(asset_name: str, *, current_session: Optional[str],
                           operator: str, vacate_method: str) -> str:
	"""Close the Venue Session currently attached to an asset.

	Caller passes `current_session` from the lock's row dict so we don't
	re-query under the lock. Throws if current_session is falsy.
	"""
	if not current_session:
		frappe.throw(_("Asset {0} has no current session to close.").format(asset_name))
	session = frappe.get_doc("Venue Session", current_session)
	# 3-AI review 2026-04-10: defensive cross-doctype invariant checks. The
	# asset_status_lock guards the asset row but not the linked session row,
	# so explicitly verify the session still belongs to this asset and is
	# still Active before mutating it. Catches drift from manual SQL edits,
	# partial backfills, or future bugs that double-close a session.
	if session.venue_asset != asset_name:
		frappe.throw(_("Session {0} belongs to {1}, not {2}.")
		             .format(current_session, session.venue_asset, asset_name))
	if session.status != "Active":
		frappe.throw(_("Session {0} is already {1} — cannot close again.")
		             .format(current_session, session.status))
	session.session_end = frappe.utils.now_datetime()
	session.operator_vacate = operator
	session.vacate_method = vacate_method
	session.status = "Completed"
	session.save(ignore_permissions=True)
	return session.name


def _set_vacated_timestamp(asset_name: str) -> None:
	frappe.db.set_value("Venue Asset", asset_name,
	                    "last_vacated_at", frappe.utils.now_datetime())


# ---------------------------------------------------------------------------
# Mark Clean (Dirty → Available) — Task 6
# ---------------------------------------------------------------------------


def mark_asset_clean(
	asset_name: str,
	*,
	operator: str,
	bulk_reason: Optional[str] = None,
) -> None:
	"""Dirty → Available.

	`bulk_reason`, when provided, is written to the Asset Status Log row's
	reason field (DEC-054 §5). Used by the bulk Mark All Clean flow to tag
	which sweep a given transition belonged to. Single-asset calls pass None.
	"""
	from hamilton_erp.locks import asset_status_lock
	from hamilton_erp.realtime import publish_status_change

	with asset_status_lock(asset_name, "clean") as row:
		_require_transition(row, current="Dirty", target="Available",
		                    asset_name=asset_name)
		_set_asset_status(
			asset_name,
			new_status="Available",
			session=None,
			log_reason=bulk_reason,
			operator=operator,
			previous="Dirty",
			expected_version=row["version"],
		)
		_set_cleaned_timestamp(asset_name)
	publish_status_change(asset_name, previous_status="Dirty")


# Parallel to `_set_vacated_timestamp`. Not folded into `_set_asset_status`
# to keep that function's kwargs bounded — two status-specific timestamp
# helpers is cheaper than a 10-kwarg core mutator. Reused by
# `mark_asset_clean` (Task 6) and `return_asset_to_service` (Task 8); the
# helper pair plateaus at two because OOS entry itself (Task 7) touches no
# `last_*_at` field. ChatGPT/Grok review 2026-04-10.
def _set_cleaned_timestamp(asset_name: str) -> None:
	frappe.db.set_value("Venue Asset", asset_name,
	                    "last_cleaned_at", frappe.utils.now_datetime())


# ---------------------------------------------------------------------------
# Set Out of Service (any state except OOS → Out of Service) — Task 7
# ---------------------------------------------------------------------------


def set_asset_out_of_service(asset_name: str, *, operator: str, reason: str) -> None:
	"""Any state (except OOS) → Out of Service. Reason is mandatory.

	OOS is the only transition that can be entered from multiple source states
	(Available, Occupied, Dirty). When entered from Occupied, the current
	Venue Session is auto-closed with vacate_method="Discovery on Rounds"
	(the operator didn't return a key; we discovered it during rounds).
	"""
	# Defense-in-depth: the VenueAsset controller's _validate_reason_for_oos
	# also rejects whitespace-only reasons at save time, but guarding here
	# avoids acquiring the Redis lock for an obviously-bad call.
	if not reason or not reason.strip():
		frappe.throw(_("A reason is required to set an asset Out of Service."))
	from hamilton_erp.locks import asset_status_lock
	from hamilton_erp.realtime import publish_status_change

	with asset_status_lock(asset_name, "oos") as row:
		previous = row["status"]
		_require_oos_entry(row, asset_name=asset_name)
		# NOTE: when previous == Occupied, _close_current_session runs BEFORE
		# _set_asset_status. A throw from _set_asset_status (e.g. hypothetical
		# version-CAS failure) would leave the Venue Session already marked
		# Completed — the request-level transaction rolls it back in a normal
		# HTTP call path. Programmatic callers MUST NOT wrap this in try/except;
		# let exceptions propagate to trigger rollback. Matches the Task 5
		# vacate_session pattern.
		if previous == "Occupied":
			current_session = row["current_session"]
			_close_current_session(
				asset_name,
				current_session=current_session,
				operator=operator,
				vacate_method="Discovery on Rounds",
			)
			log_venue_session = current_session
		else:
			log_venue_session = None
		_set_asset_status(
			asset_name,
			new_status="Out of Service",
			session=None,
			log_venue_session=log_venue_session,
			log_reason=reason,
			operator=operator,
			previous=previous,
			expected_version=row["version"],
		)
	publish_status_change(asset_name, previous_status=previous)


# ---------------------------------------------------------------------------
# Return to Service (Out of Service → Available) — Task 8
# ---------------------------------------------------------------------------


def return_asset_to_service(asset_name: str, *, operator: str, reason: str) -> None:
	"""Out of Service → Available. Reason is mandatory.

	Parallels mark_asset_clean in shape: single-branch lock body terminated
	with _set_cleaned_timestamp (returning an asset from OOS is effectively
	the end of a cleaning/repair cycle, so last_cleaned_at is the right
	timestamp to bump).

	The stale OOS reason on the asset is cleared centrally by
	_set_asset_status's `elif previous == "Out of Service"` branch — do NOT
	duplicate that logic here (Gemini review 2026-04-10).
	"""
	# Defense-in-depth: mirror set_asset_out_of_service's pre-lock reason
	# guard so obviously-bad calls never acquire the Redis lock.
	if not reason or not reason.strip():
		frappe.throw(_("A reason is required to return an asset to service."))
	from hamilton_erp.locks import asset_status_lock
	from hamilton_erp.realtime import publish_status_change

	with asset_status_lock(asset_name, "return") as row:
		_require_transition(row, current="Out of Service", target="Available",
		                    asset_name=asset_name)
		_set_asset_status(
			asset_name,
			new_status="Available",
			session=None,
			log_reason=reason,
			operator=operator,
			previous="Out of Service",
			expected_version=row["version"],
		)
		_set_cleaned_timestamp(asset_name)
	publish_status_change(asset_name, previous_status="Out of Service")


# ---------------------------------------------------------------------------
# Session number generator (DEC-033 + Q9) — Task 9
# ---------------------------------------------------------------------------
#
# Returns strings in the form `{d}-{m}-{y}---{NNNN}`, e.g. "9-4-2026---0001".
# Day and month are NOT zero-padded (per DEC-033); the trailing sequence IS
# zero-padded to 4 digits (widened from 3 on 2026-04-10, Task 11, to eliminate
# the lexicographic>999 sort risk in _db_max_seq_for_prefix). The daily
# sequence is scoped by KEY NAME — the Redis key's prefix changes at midnight,
# so a new day starts fresh without relying on TTL-based expiry. The 48h TTL
# is just garbage collection.
#
# Race-safety notes:
#   - INCR is atomic, so two concurrent callers at steady state always get
#     consecutive values with no gap.
#   - On the cold-start path, two callers may both compute db_max and both
#     call SET with nx=True. Only the first SET wins; the second no-ops
#     (nx means "only if not exists"). Both callers then INCR, which is
#     still atomic, so the two callers get consecutive values starting from
#     db_max + 1.
#   - The raw .set() / .get() / .incr() / .delete() methods are used directly
#     (inherited from redis.Redis) instead of frappe.cache() wrappers like
#     .exists() or .delete_value(), because the wrappers prefix keys via
#     make_key() while the raw methods do not. locks.py uses the same raw
#     style — see hamilton_erp/locks.py for the established pattern.

_SESSION_KEY_TTL_MS = 48 * 60 * 60 * 1000  # 48 hours


def _next_session_number() -> str:
	"""Return the next session number for today in DEC-033 format.

	Format: `{d}-{m}-{y}---{NNNN}`, e.g. "9-4-2026---0001". Day/month are NOT
	zero-padded; the trailing sequence IS zero-padded to 4 digits (widened
	from 3 on 2026-04-10, Task 11, per the Task 9 3-AI review).

	Sequence is reset by KEY NAME (the date-based prefix changes at midnight),
	not by TTL — the 48h TTL is just garbage collection so stale keys evaporate.

	Race-safety: when the Redis key is cold, two callers may both compute
	`db_max` and both call SET with nx=True. Only the first SET wins; the
	second no-ops. Both callers then INCR, which is atomic, so the two
	callers get consecutive values starting from `db_max + 1`.
	"""
	# nowdate() returns "YYYY-MM-DD" regardless of local format preferences.
	year, month, day = frappe.utils.nowdate().split("-")
	d, m, y = int(day), int(month), int(year)
	prefix = f"{d}-{m}-{y}"
	key = f"hamilton:session_seq:{prefix}"
	cache = frappe.cache()
	# Fail-closed on Redis errors — matches locks.py LockContentionError pattern.
	# A transient Redis fault becomes a user-friendly ValidationError rather than
	# a bare redis.ConnectionError stack trace surfacing to the operator.
	# Raw .get() — no make_key() prefix, matches locks.py's raw usage.
	# A missing key returns None; we cannot use cache.exists() here because
	# it prefixes via make_key() and would not match our raw .set() path.
	try:
		if cache.get(key) is None:
			# DB call kept INSIDE the try: the broad except below will wrap
			# a DB failure in the same user-friendly message. That's a minor
			# diagnostic loss (DB errors masquerade as "session service
			# unavailable"), but acceptable — a failing SELECT here means
			# the subsequent Venue Session INSERT would fail anyway, and
			# the real error surfaces from that call's stack trace.
			db_max = _db_max_seq_for_prefix(prefix)
			# nx=True so only the first cold-start caller seeds the key; later
			# callers in a tight race no-op the SET and proceed to INCR.
			# px=TTL garbage-collects stale keys (NOT for sequence expiry).
			cache.set(key, db_max, nx=True, px=_SESSION_KEY_TTL_MS)
		# INCR is atomic — produces consecutive values even under concurrency.
		# redis-py returns int; cast defensively in case the wrapper ever changes.
		seq = int(cache.incr(key))
		# Overflow guard (Task 11 3-AI review): the :04d format below caps at
		# 9999. If the daily sequence ever exceeds that, the format still
		# renders (Python %d never truncates), but ordering and visual width
		# break. We do NOT raise — the UNIQUE constraint and retry loop
		# downstream handle correctness. Just warn loudly so ops notices.
		if seq > 9999:
			frappe.logger().warning(
				f"_next_session_number: session sequence overflow at {seq} "
				f"for {key} — contact admin. Daily limit exceeded."
			)
	except Exception as exc:
		frappe.logger().warning(
			f"_next_session_number: Redis failure for {key}: {exc}"
		)
		raise frappe.ValidationError(
			_("Session number service temporarily unavailable. Please try again.")
		)
	return f"{prefix}---{seq:04d}"


def _db_max_seq_for_prefix(prefix: str) -> int:
	"""Return the highest trailing NNNN for today's prefix in `tabVenue Session`.

	Used as a cold-Redis fallback so a mid-day Redis flush cannot restart the
	daily sequence at 0001 and collide with already-persisted rows. Returns 0
	when no rows exist for today's prefix — the subsequent INCR then yields 1,
	which formats as "0001" and matches the first-call-of-the-day invariant.

	The ORDER BY is lexicographic, but because the trailing NNNN is always
	zero-padded to 4 digits, lexicographic ordering matches numeric ordering
	for sequences 0000–9999. DEC-033 caps daily sessions well under that
	ceiling, so no additional numeric sort is needed.
	"""
	row = frappe.db.sql(
		"SELECT session_number FROM `tabVenue Session` "
		"WHERE session_number LIKE %s "
		"ORDER BY session_number DESC LIMIT 1",
		(f"{prefix}---%",),
		as_dict=True,
	)
	if not row:
		return 0
	raw_session_number = row[0]["session_number"]
	tail = raw_session_number.rsplit("---", 1)[-1]
	try:
		return int(tail)
	except ValueError:
		# Defensive: if somehow a malformed session_number sneaks through,
		# fall back to 0 rather than crash the assignment flow. The INCR
		# path will then start at 1, which may collide with existing rows;
		# Task 11 adds a DB uniqueness constraint on session_number so that
		# collision surfaces as UniqueValidationError the caller can retry.
		#
		# Log via frappe.log_error so production operators can see the bad
		# row in the Error Log doctype — silent fallback would otherwise
		# mask a data-integrity issue indefinitely.
		frappe.log_error(
			message=(
				f"_db_max_seq_for_prefix: malformed session_number "
				f"{raw_session_number!r} for prefix {prefix!r} — trailing "
				f"segment {tail!r} did not parse as int. Falling back to 0."
			),
			title="Malformed session_number in DB",
		)
		return 0
