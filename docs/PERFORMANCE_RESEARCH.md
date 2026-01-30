# Performance Research (2026-01-23)

## Scope

Reviewed the deck build pipeline with focus on CPU overhead, I/O contention, and redundant network calls.

## Key Bottlenecks Found

1. **Per-row throttle delay** in `process_row()` imposed a fixed 50ms delay even when no backoff was needed. With large vocab lists this adds minutes of idle time.
2. **Sentence audio was never cached**, so repeated builds re-generated all sentence audio even if files already existed.
3. **`iterrows()` overhead** for large DataFrames; it is significantly slower than `itertuples()` for read-heavy iteration.
4. **Task allocation for cached items** still created no-op coroutines, adding scheduling overhead per row.
5. **Row-wide failures from single task exceptions**: one failed fetch could raise and mark the whole row failed, reducing throughput and increasing retries.

## Changes Implemented

- **Removed fixed 50ms stagger** and replaced with a zero-delay yield (keeps cooperative scheduling without throttling).
- **Added cache checks for sentence audio** to fully skip TTS when already generated.
- **Switched to `itertuples()` iteration** for faster row processing.
- **Created a lightweight row accessor** to support both Series and namedtuples without branching at call sites.
- **Avoided creating tasks for cached items**, reducing coroutine overhead.
- **Handled task exceptions per resource**, preventing a single failure from aborting a full row.

## Expected Impact (Qualitative)

- **Large builds (1000+ rows)**: significantly reduced idle time (no 50ms per-row delay).
- **Rebuilds with cache**: dramatic improvement because sentence audio is now skipped when cached.
- **Lower CPU overhead**: faster DataFrame iteration and fewer coroutine allocations.

## Follow‑up Opportunities (Optional)

- **Introduce batch-level concurrency tuning** (e.g., adaptive batch size based on latency).
- **Add file-hash based cache validation** to detect outdated audio or images when content changes.
- **Optional SQLite backend** in GUI flow for faster CRUD and filtering (already supported in `VocabularyService`).

## Files Touched

- [src/deck/builder.py](../src/deck/builder.py)
