# Changes to `night_info.py`

Date: 2026-06-25

Summary of an evaluation pass for correctness, bugs, and inaccuracies, plus the
fixes applied.

## Fixes applied

### 1. Long-winter-night edge bug (behavioral fix)
**Where:** `find_best_event`, sunset branch (~line 175)

**Before:** the "tonight" sunset was taken as the most recent past sunset only if
it occurred less than **11 hours** ago.

**Problem:** winter / higher-latitude nights can exceed 11 hours of darkness. On a
*live* run (no `--date`) in the early-morning hours while still dark, the previous
sunset was already >11h in the past, so the script skipped ahead to the *upcoming*
evening's sunset and reported the **next** night instead of the one in progress.

**Fix:** raised the threshold from `11 * 3600` to `16 * 3600` (≈16 hours), which
covers realistic long-night lengths while still preferring the current day's
sunset once well into daytime.

### 2. Inconsistent threshold documentation (inaccuracy fix)
**Where:** `find_best_event` docstring and inline comment

The docstring said "~18h", the inline comment said "~14 hours", and the code used
11h — three different numbers. All three are now reconciled to "~16 hours" to
match the corrected code.

### 3. Removed dead code (cleanup)
**Where:** former `find_sunset`, `find_dusk`, `find_dawn` (~50 lines)

These three functions were never called. Their docstrings claimed they were "kept
for ... --date mode fallback," but `--date` mode also routes through
`find_best_event`, so there was no fallback path. Deleted.

The `dusk`/`dawn` imports are still required (used by `find_best_event` and
`find_next_dawn_after`), so the import line was left unchanged.

## Notes / non-issues observed (not changed)

- **Moon illumination is approximate.** It takes a cosine of astral's 28-unit
  phase value, but astral's phase is itself a simplified month (the real synodic
  month is ≈29.53 days). The reported `% illuminated` can be off by a few percent.
  The phase *name* bucketing is correct. Left as-is; acceptable for casual use.
- `now = dt.datetime.now(tz)` is computed even in `--date` mode where it is
  unused — harmless, left as-is.
- `get_location_from_ip` does not catch `TypeError`, but a `"success"` status from
  ip-api.com guarantees the `lat`/`lon` fields exist, so it cannot trigger in
  practice. Left as-is.

## Verification

- `ast.parse` confirms the file still parses.
- Re-ran normal, winter (`--date 2026-12-21`), and polar-summer cases; all produce
  correct output. The winter table still reports 11h 25m of darkness anchored to
  the Dec 21 sunset.
