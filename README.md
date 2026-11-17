# GTA VI Twitch forecaster — poker-mid branch (iteration 6)

Variant of the v5-ship model (`main`, commit c3e2c3a8) with the anchor bet
turned up one notch: the boost threshold is lowered (0.3 → 0.175) and the
boost raised (2.0 → 2.5), so the bet fires on warm anchors too, not only
Wolverine-hot ones. Everything else is identical to the ship (base scale
1.375, boost cap 0.20, shift 0.125, upper 1.0, ln(v1) cap 12.6).

## Scores (verified on the real files)

| Model | Practice | LOPO-rest | Poker | S1 expl. | S6 expl. | Super-Wolv. | S9 fail | S10 fail | LOO-C |
|---|---|---|---|---|---|---|---|---|---|
| v5-ship (`main`) | 0.1343 | 3/4 | 0.1826 | 0.477 | 0.398 | 0.236 | 0.290 | 0.257 | 0.2165 |
| **poker-mid (this branch)** | **0.1363** | **3/4** | **0.1706** | **0.439** | **0.386** | **0.214** | **0.298** | **0.264** | **0.2209** |
| v5-full (`poker` branch) | 0.1473 | 0/4 | 0.1588 | 0.360 | 0.300 | 0.178 | 0.382 | 0.335 | 0.2311 |

Per-case practice: p00 0.1376 / p01 0.1214 / p02 0.1074 / p03 0.1786.

## Status

Chambered, NOT the watch queue's entry. It does not replace the ship
under the ship rule (practice 0.1363 > 0.1343). It is the best
LOPO-healthy middle point on the ship↔full frontier: the best final-day
poker score among candidates that keep LOPO-rest 3/4, with failure modes
essentially tied with the ship (S9 0.298 vs 0.290). The parent decides
whether it goes in if the quota opens wide — it is the rank-1 bet for a
day that is explosive but not maximally so. The full `poker` branch is the
maximum bet; the ship is the defensible one.

See `analysis/ITERATION6.md` (in the parent's workdir, not this repo)
for the full frontier table and the rejected hour-ramped boost.
