# Database Sync Behavior - Clear Rules

This document explains **exactly** which databases get updated in each scenario.

---

## TL;DR - Quick Reference

| Command | Stats Go To | Aggregations Updated In |
|---------|------------|------------------------|
| `python main.py --mode collect` | Supabase | Supabase |
| `python main.py --mode collect --use-local-db` | Supabase + Local | Supabase + Local |
| `python main.py --mode collect --use-local-db --local-stats` | Local ONLY | Local ONLY |
| `python main.py --mode backfill` | N/A | Supabase |
| `python main.py --mode backfill --use-local-db` | N/A | Supabase + Local |
| `python main.py --mode backfill --use-local-db --local-stats` | N/A | Local ONLY |

---

## Detailed Explanation

### The Three Modes

1. **Default (no flags)** - Supabase only
2. **`--use-local-db`** - Supabase AND local (both)
3. **`--use-local-db --local-stats`** - Local ONLY (save Supabase costs)

### Flag Meanings

**`--use-local-db`**
- Enables local database in addition to Supabase
- Think of it as "also use local DB"
- Supabase is ALWAYS used unless you add `--local-stats`

**`--local-stats`**
- Changes behavior to LOCAL ONLY (skips Supabase)
- **Requires** `--use-local-db` (otherwise there's nowhere to store data!)
- Use this when you want to save Supabase storage costs

---

## Collection Mode (`--mode collect`)

### No Flags (Default)
```bash
python main.py --mode collect --week 10
```
**What happens:**
- ✅ Teams/players → Supabase
- ✅ Games → Supabase
- ✅ Stats → Supabase
- ✅ Aggregations → Supabase (auto-refreshed)
- ❌ Nothing goes to local DB

### With `--use-local-db`
```bash
python main.py --mode collect --week 10 --use-local-db
```
**What happens:**
- ✅ Teams/players → Supabase AND local
- ✅ Games → Supabase AND local
- ✅ Stats → Supabase AND local
- ✅ Aggregations → Supabase AND local (both auto-refreshed)

### With `--use-local-db --local-stats`
```bash
python main.py --mode collect --week 10 --use-local-db --local-stats
```
**What happens:**
- ✅ Teams/players → Supabase (metadata always goes to Supabase)
- ✅ Games → Supabase (metadata always goes to Supabase)
- ✅ Stats → Local ONLY (this is the key difference!)
- ✅ Aggregations → Local ONLY
- ❌ Stats do NOT go to Supabase (saves storage costs)

**Why this is useful:**
- Your app can still query teams/players/games from Supabase
- Heavy stats data stays local
- Saves Supabase storage costs while keeping metadata accessible

---

## Backfill Mode (`--mode backfill`)

Regenerates aggregation tables from existing stats data.

### No Flags (Default)
```bash
python main.py --mode backfill
```
**What happens:**
- ✅ Reads games from Supabase
- ✅ Regenerates aggregations in Supabase
- ❌ Local DB not touched

**Use when:**
- You collected data without `--use-local-db`
- All your stats are in Supabase
- You need to rebuild Supabase aggregations

### With `--use-local-db`
```bash
python main.py --mode backfill --use-local-db
```
**What happens:**
- ✅ Reads games from Supabase
- ✅ Regenerates aggregations in Supabase
- ✅ Also regenerates aggregations in local DB
- Both databases are backfilled

**Use when:**
- You collected data with `--use-local-db`
- Stats exist in both databases
- You need to rebuild aggregations in both

### With `--use-local-db --local-stats`
```bash
python main.py --mode backfill --use-local-db --local-stats
```
**What happens:**
- ✅ Reads games from local DB
- ✅ Regenerates aggregations in local DB ONLY
- ❌ Supabase not touched

**Use when:**
- You collected data with `--use-local-db --local-stats`
- All stats are in local DB only
- You need to rebuild local aggregations

---

## Common Workflows

### Workflow 1: Supabase Only (Simple, Cloud-Based)
```bash
# Seed initial data
python main.py --mode seed

# Collect weekly data
python main.py --mode collect --week 10

# Backfill if needed
python main.py --mode backfill
```
**Result:** Everything in Supabase, easy to access from anywhere

---

### Workflow 2: Supabase + Local Sync (Full Redundancy)
```bash
# Seed initial data
python main.py --mode seed --use-local-db

# Collect weekly data
python main.py --mode collect --week 10 --use-local-db

# Backfill if needed
python main.py --mode backfill --use-local-db
```
**Result:** Identical data in both databases, full redundancy

---

### Workflow 3: Local Stats, Supabase Metadata (Cost-Efficient)
```bash
# Seed initial data (teams/players go to Supabase)
python main.py --mode seed --use-local-db

# Collect weekly data (stats go to local only)
python main.py --mode collect --week 10 --use-local-db --local-stats

# Backfill local aggregations if needed
python main.py --mode backfill --use-local-db --local-stats
```
**Result:**
- Supabase: teams, players, games (metadata)
- Local: stats, aggregations (heavy data)
- Best of both worlds: accessible metadata, local analytics

---

## Why `position_stat_distribution_agg` Might Be Empty

This table is populated by the `refresh_aggregations_for_game()` function, which is called:

1. **Automatically** after stats are inserted (during `--mode collect`)
2. **Manually** when you run `--mode backfill`

**If it's empty, it means:**
- No stats have been inserted yet, OR
- Stats were inserted but aggregations weren't refreshed, OR
- The SQL function failed (check logs for errors)

**To fix:**
```bash
# Run backfill to regenerate
python main.py --mode backfill --use-local-db
```

---

## Troubleshooting

### "Why is my Supabase aggregation table empty?"
**Possible reasons:**
1. You used `--local-stats` mode (stats only went to local DB)
2. You ran `--mode backfill --use-local-db` (only backfilled local)
3. The RPC function failed (check Supabase logs)

**Solution:**
```bash
# Backfill Supabase (without --local-stats)
python main.py --mode backfill
```

### "Why is my local aggregation table empty?"
**Possible reasons:**
1. You didn't use `--use-local-db` flag
2. You ran `--mode backfill` without `--use-local-db`
3. The SQL function failed (check local DB logs)

**Solution:**
```bash
# Backfill local DB
python main.py --mode backfill --use-local-db --local-stats
```

### "Which database should I query for my app?"
**Depends on your collection mode:**

- If you collect with `--local-stats`: Query Supabase for metadata, local for stats
- If you collect without `--local-stats`: Query Supabase for everything
- If you collect with `--use-local-db` (no --local-stats): Query either (they're identical)

---

## Summary

**Think of it this way:**

- **No flags** = Supabase is your single source of truth
- **`--use-local-db`** = Local is a mirror of Supabase
- **`--use-local-db --local-stats`** = Supabase has metadata, local has stats

The behavior is **consistent** across all modes (`collect`, `backfill`, `full`).
