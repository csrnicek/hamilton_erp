#!/usr/bin/env bash
# Redis cache (13000) + queue (11000) port reachability check.
# Demoted from hamilton_erp/test_environment_health.py 2026-05-01.
# Run manually when test suite is timing out at 30s+ — confirms Redis is alive.
set -euo pipefail
nc -zv localhost 13000 && echo "✓ Redis cache (13000) reachable"
nc -zv localhost 11000 && echo "✓ Redis queue (11000) reachable"
