# Findings & Fixes

## 1. Dashboard showed fake numbers (Client A: "totals don't match")
- **Symptom:** Sunset's Beach House Alpha showed USD 1,000.00 / 3 bookings; the DB holds 2,250.00 / 4.
- **Root cause:** `DatabasePool` built its URL from settings that don't exist, used the sync `QueuePool` with an async engine, `get_session` was `async` (so `async with` failed), and `greenlet` was missing. Every query failed and `calculate_total_revenue` silently returned hardcoded mock data.
- **Fix:** Build the URL from `DATABASE_URL`, use the default async pool, make `get_session` sync, install `sqlalchemy[asyncio]`, reuse the shared pool. Remove the mock fallback; the API now returns 503 instead of invented figures.

## 2. Cross-tenant data leak (Client B: "numbers from another company")
- **Root cause:** The revenue cache key was `revenue:{property_id}`. Property IDs are only unique per tenant (`prop-001` exists for both), so whichever tenant loaded first had its totals served to the other for 5 minutes.
- **Fix:** Key is now `revenue:{tenant_id}:{property_id}:{period}`.
- **Related:** The frontend hardcoded every property name, so Ocean saw Sunset's "Beach House Alpha" label. Added `GET /api/v1/dashboard/properties` (tenant-scoped) and the dropdown now uses it. Requests without a tenant get a 403 instead of falling back to `default_tenant`.

## 3. Monthly totals off because of time zones (Client A: March)
- **Root cause:** Month boundaries were naive UTC. `res-tz-1` checks in `2024-02-29 23:30 UTC`, which is 1 March 00:30 in Paris (the property's time zone), so it was counted in February. `calculate_monthly_revenue` was also a stub that returned 0 and ignored the tenant.
- **Fix:** The summary accepts `month`/`year` and filters on `check_in_date AT TIME ZONE p.timezone`. March 2024 for Sunset prop-001 is 2,250.00 / 4 (UTC gives 1,000.00 / 3). Added a month picker to the dashboard.

## 4. Cents "slightly off" (finance team)
- **Root cause:** Amounts are `NUMERIC(10,3)` (sub-cent), and the total was converted straight to `float` and rounded in JS (`Math.round(x*100)/100`), which drifts with binary floating point.
- **Fix:** Totals are rounded to cents with `Decimal` (`ROUND_HALF_UP`) on the server before being serialised.

## Verify
```bash
docker compose up --build
```
Log in as each client at http://localhost:3000. Each client sees only its own properties and totals, and setting the month to 2024-03 shows local-time March revenue.
