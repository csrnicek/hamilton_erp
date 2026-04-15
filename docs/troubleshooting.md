## Common Issues and Solutions
Tests fail with setUpClass errors
Symptom: Phase 0 stub doctypes (asset_status_log, comp_admission_log, cash_drop, venue_session, shift_record, cash_reconciliation) fail with setUpClass errors. Cause: Pre-existing issue — these doctypes don't set IGNORE_TEST_RECORD_DEPENDENCIES. Action: Ignore these. They are out of scope. Only fix if they appear in the 5 core test modules.

bench run-tests only runs the last --module
Symptom: Running multiple --module flags only runs the last one. Fix: Run each module as a separate bench command. Use /run-tests slash command which does this correctly.

Redis lock contention error during tests
Symptom: LockContentionError on an asset that should be free. Cause: A previous test crashed and left a Redis key. The key has a 15s TTL and will expire. Fix: Wait 15 seconds and retry. Or flush Redis: redis-cli FLUSHDB (test site only — NEVER on production).

TimestampMismatchError on asset save
Symptom: frappe.TimestampMismatchError when saving a Venue Asset. Cause: Two instances of the same doc were loaded, one saved, the other tried to save with a stale modified timestamp. Fix: Always re-fetch with frappe.get_doc() inside the lock — never use a cached instance.

session_number not populated on Venue Session
Symptom: session.session_number is empty after insert. Cause: before_insert hook not running, or Redis down. Fix: Check Redis is running (bench doctor). Check VenueSession controller has before_insert defined. Run bench migrate if doctype JSON was changed.

Asset stuck in wrong status after failed operation
Symptom: Asset shows Occupied but no active session exists. Cause: Transaction rolled back but Redis key was not released, or DB state corrupted manually. Fix: Use /bug-triage. Check Asset Status Log for last known good state. Manually correct via bench console with frappe.db.set_value() — document the correction in a comment.

Frappe Cloud deploy not reflecting latest code
Symptom: hamilton-erp.v.frappe.cloud shows old behavior after push. Cause: Frappe Cloud auto-deploy takes 2-3 minutes. Or bench migrate did not run. Fix: Wait 3 minutes. Check Frappe Cloud dashboard for deploy status. If stuck, trigger manual redeploy from dashboard.

bench migrate fails on venue_session.json change
Symptom: Migration error when adding unique constraint or read_only field. Cause: Existing data violates the new constraint (duplicate session_numbers). Fix: Check for duplicates: frappe.db.sql("SELECT session_number, COUNT(*) FROM tabVenue Session GROUP BY session_number HAVING COUNT(*) > 1"). Fix duplicates before migrating.

MariaDB "too many connections" error
Symptom: Can't connect to MySQL server — too many connections. Cause: Connection pool exhausted, usually from a crashed worker that didn't close connections. Fix: sudo systemctl restart mariadb on local bench. On Frappe Cloud, contact support or restart bench via dashboard.
