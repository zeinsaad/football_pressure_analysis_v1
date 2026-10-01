# Post-Match Pressing Report — Barcelona vs Atlético

**Tracked window: 46:53 of live play | 26 stoppages (450.7s excluded)**

---

## 1. Pressing Identity & Philosophy

These are two opposed out-of-possession models, and almost every metric in the payload separates them along the same axis.

**Barcelona pressed high, early, and selectively.** Their last-3 defensive line sat at a mean **47.8m** from their own goal (median 51.4m), effectively on the halfway line. Atlético's sat at **28.6m** (median 24.8m), a gap of roughly **19m** between the two teams' resting defensive platforms. That single number frames everything else: Barca defended the opponent's half, Atlético defended their own.

The zone distribution confirms it rather than merely echoing it. **46.9% of Barca's pressure came in the attacking third** against **10.0% for Atlético**, while Atlético concentrated **52.9% in the middle third and 37.2% in their own third**. Territory-weighted, Barca's press scores **18.4% of theoretical maximum** against Atlético's **11.4%** — a 60% gap that is about *where* pressure landed, not how much of it there was.

The PPDA figures are the sharpest split: **Barca 2.4 (119 passes allowed / 49 defensive actions)** versus **Atlético 6.3 (158 / 25)**. Note the asymmetry in the numerator and denominator simultaneously — Barca allowed fewer passes *and* made nearly twice as many actions. Read alongside a **40.0% press-event regain rate** (42 of 105 events) versus Atlético's **25.7%** (37 of 144), the picture is a press designed to win the ball rather than to delay.

The most revealing comparison is volume against yield. **Atlético logged more flagged pressing frames than Barca (5,324 vs 4,311)** yet produced fewer regains from them. Atlético were not passive. They were busy in low-value areas. Barca's press was rarer in raw frame terms and roughly twice as productive per unit of effort.

One caveat on PPDA specifically: with ball-carrier coverage at **47.6%**, both PPDA values are built on a thinned event set and sit far below typical full-tracking benchmarks. They are valid *against each other* in this match. They should not be compared to league-wide PPDA tables.

---

## 2. Zone-by-Zone Pressing Effectiveness

Re-oriented to each pressing team's own zone labels:

| | Barca press | Atlético press |
|---|---|---|
| In opponent's build-up area | **38.9%** turnover (n=54) | **25.8%** turnover (n=31) |
| Middle third | **31.7%** turnover (n=41) | **17.2%** turnover (n=64) |
| Pinned in own third | 50.0% turnover (n=8) | 23.1% turnover (n=13) |

Barca out-performed Atlético in every zone, and the margin is widest exactly where they invested most. The **54 Atlético on-ball events in Atlético's own third** are the single largest pressed-event bucket in the match, and Barca disrupted **70.4%** and turned over **38.9%** of them. That is the engine of their whole defensive performance: a high press with real volume behind it, not a token first-man trigger.

Atlético's mirror-image bucket is their middle-third press, **64 Barca events**, but it yielded only a **17.2% turnover rate**, the lowest figure in the table. Their block absorbed play in midfield without converting contact into possession.

The two "pinned back" rows (**n=8 and n=13**) are too thin to support conclusions. Barca's headline 50% turnover when defending deep rests on eight events and should be ignored in planning terms. Flagging it here only so it isn't read as a strength.

Spatially, the heatmaps align with the trigger data. Barca's densest cell is **x 90–95, y 30–35 (127 events, 3.15% of their total)** — central, deep inside Atlético's defensive third, right where a goalkeeper-to-centre-back build-up would start. Atlético's densest cells cluster instead around **x 70–75, y 0–15 (174 and 120 events, 3.30% and 2.28%)**: wide, on the defensive-third boundary. That is a mid-block funnelling play toward the touchline and engaging at the edge of the block rather than in front of the opponent's goalkeeper.

The reception triggers corroborate this. Barca followed **73.4% of Atlético receptions** with a press, against **65.5%** the other way, and the Atlético receptions they were pressing were disproportionately **deep in their own third (46.9%)**, **after a backward pass (53.1%)**, and **on static touches (35.2%)**. Barca were hunting the backward pass in build-up. Atlético's equivalent trigger profile against Barca is far flatter (deep own third 17.5%, backward pass 41.7%), consistent with a block that waits for play to arrive.

---

## 3. Defensive Shape & Line Height

Barca's out-of-possession block was **22.3m deep and 36.7m wide**, covering a mean **848 m²**. Atlético's was **19.3m deep and 36.2m wide**, covering **721 m²**. Widths are effectively identical; the difference is entirely vertical.

This is the expected trade-off. Atlético bought vertical compactness (**15% less area**) at the cost of 19m of territory, and it was sound in its own terms: Barca's progression rate under Atlético pressure was only **24.8%**, and Barca were pushed backward on **27.5%** of pressured actions versus 14.5% unpressured. The block did what a block does.

What it did not do was win the ball, and that is the whole story of this match. Being compact 28m from your own goal means every regain starts 70m from the opponent's.

Both teams tightened when pressing. Barca's covered area fell from **863 m² to 764 m² (−11.5%)** on flagged pressure frames; Atlético's from **736 m² to 675 m² (−8.3%)**. Barca compressed harder, which is consistent with a press that commits bodies rather than shapes.

One structural note worth carrying into any tactical conclusion: both teams' line-height standard deviations are large (**Barca 19.8m, Atlético 18.1m** on the last-3). Neither team held a rigid line. These are mean platforms with substantial swing, so "Barca's high line" describes a tendency, not a fixed reference.

---

## 4. Counter-Pressing Effectiveness

On immediate reaction to losing the ball, Barca were better by a factor of more than two: **37.1% regain rate on fast counter-presses (13 of 35)** against Atlético's **16.7% (4 of 24)**. Slow responses collapsed for both (Barca 18.2%, Atlético 6.2%).

The clearest evidence chain in the payload runs through the **3:24** mark. Barca lost possession at **3:24**, the pressure flag was active within a single frame, and the resulting press ran **3:24–3:40** with a mean of **1.35 pressers and a peak of 3**, ending in a regain. That is the full Barca counter-press cycle in one sequence: immediate reaction, multiple bodies, ball recovered. Worth noting the honest technicality — the counter-press row logs `regained_within_window: false` while the press event logs `regained_ball: true`, meaning the recovery came after the strict counter-press window but inside the same pressure phase.

A second chain at **36:09**: Barca lost the ball, pressure registered immediately, and Atlético's ensuing possession was logged as **100% under pressure** across its full 1.0s before breaking down.

Atlético's one comparable moment is at **30:43**, a fast counter-press that did regain within the window. It is their only entry in the fastest-counter-press set, against four for Barca.

Two cautions. First, all five fastest counter-presses register at **0.04s**, which is one frame at 25fps. This is the measurement floor. It does not mean players reacted in 40 milliseconds; it means the pressure condition was already satisfied at the instant of the turnover, so the press was pre-loaded rather than reactive. That is still tactically meaningful, but "instant reaction time" is the wrong reading.

Second, Atlético's **"never pressed" category shows a 40.0% regain rate (6 of 15)**, higher than their fast-response rate. This should not be read as evidence that not pressing worked. With 15 events and a mechanism that plausibly includes balls going dead or Barca conceding possession unforced, it is noise sitting on a different causal pathway from a counter-press regain.

---

## 5. Passes Under Pressure & Disruption

This section is where the two presses diverge most cleanly in *kind*, not just degree.

**Barca's passing was unaffected by Atlético's pressure.** Success rate: **83.6% unpressured, 83.0% pressured** across 88 pressured passes. A 0.6pp drop is nothing.

**Atlético's passing degraded under Barca's pressure:** **77.2% to 71.2%** across 80 pressured passes. The direction is right and matches every other metric, though with n=80 a 6pp swing is not far outside sampling noise on its own. It earns confidence from consistency with the rest of the payload, not from its own significance.

The broader outcome distribution (different denominator and category scheme from pass success rate, so the two are not meant to reconcile) tells a sharper story:

- **Atlético under pressure:** interceptions jumped from **13.7% to 22.3%**, and retention after a gap collapsed from **19.6% to 7.8%**. Barca's press converted directly into intercepted ball.
- **Barca under pressure:** interceptions rose only **10.8% to 13.8%**, while forced-backward nearly doubled, **14.5% to 27.5%**. Atlético's press turned Barca around. It did not take the ball off them.

Team-level disruption follows: **73.8% of Atlético's on-ball actions were disrupted** against **62.4% of Barca's**. (Reading these by the team whose actions were disrupted, per the payload's zone-orientation convention — so the 73.8% is credit to Barca's press.)

**Containment versus theft.** Atlético's press achieved the first. Barca's achieved the second. Against an opponent that passes at 83% under pressure, containment alone does not return possession.

---

## 6. Comparative Verdict

**Barcelona's pressing was the more effective of the two, decisively, and on every dimension the payload measures.**

The case stacks without contradiction: they pressed **33.4% of opponent possession** against 26.5%; at a PPDA of **2.4** against 6.3; from a line **19m higher**; with a **40.0%** press-event regain rate against 25.7%; a **37.1%** counter-press regain rate against 16.7%; and a **38.9%** turnover rate in the opponent's build-up zone across the largest event bucket in the match. Their press cost Atlético **6pp of passing accuracy and 8.6pp more interceptions**, while Atlético's press cost Barca essentially nothing beyond a backward pass.

The mechanism behind the gap is visible in the event detail, and it is about bodies. Barca's productive pressure was multi-player: the **3:24** regain ran at up to three pressers. Their two *longest* pressure events were not. The **9.12s** phase at **16:47** averaged 0.89 pressers with 46% of lanes blocked, and the **8.6s** phase at **30:46** averaged **zero proximity pressers** with 45% lane blocking. Both ended without a regain. These are legitimate lane-blocking pressure events under the payload's definition, not data errors, and the lesson is consistent: **Barca's shadow-cover pressure held Atlético still, but only committed bodies won the ball back.** Atlético's profile shows the same pattern with less of the productive half — their two longest events (**8:54** and **14:06**) were lane-blocking with 0.17 and 0.23 mean pressers and no regain, while their one genuine swarm at **18:19** (1.58 mean, peak 3) did produce a regain.

Sustained intensity also favoured Barca. Their longest single pressure phase (9.12s) was **63% longer** than Atlético's (5.6s).

### Confidence and limits

The direction of this verdict is robust — it holds across a dozen independent metrics with no counter-signal. Three things constrain how far it travels:

1. **Ball-carrier coverage is 47.6%**, which systematically thins fast and contested sequences. Since contested transitions are exactly where counter-pressing lives, both counter-press datasets are likely undercounted, and the Barca-Atlético gap there is the number most exposed to that gap.
2. **This is a 46:53 window**, not a full match. The intensity timeline shows Barca opening at **46.0% and 38.0%** in the first two five-minute bins and falling to **11.5%** in the final partial bin, with Atlético null in that bin. Whether that is genuine fade or an artifact of a truncated, partially-covered segment cannot be determined from this payload.
3. **Player identity is fragmented (69 distinct track IDs).** This does not affect anything above, which is entirely team-level, but it means none of this can currently be attributed to individuals.

### Tactical summary for the staff

Barca ran a high, trigger-based press aimed at the backward pass in Atlético's build-up, committed multiple players to regain, and were rewarded with interceptions in dangerous territory. Atlético ran a compact wide-funnelling mid-block that successfully turned Barca backward and never took the ball off them. Against this opponent, Atlético's containment was not a containment failure. It was a recovery failure.

---

## Addendum — notes from running this prompt

Two orientation points that the methodology block doesn't cover explicitly, in case they're worth pinning down in the payload:

- **`shape_by_pressure_state.under_team_pressure`** reads as "this team is being pressed," but the shape convention restricts to out-of-possession frames, which makes that impossible. Resolved by frame counts: the `true` rows (4,311 / 5,324) match each team's own `zone_pressure_counts` totals (4,323 / 5,324, the latter exactly). So those rows are read as each team's shape *while pressing*. A rename or a one-line convention note would remove the ambiguity.
- **`disruption_rate_pct`** has no stated orientation. Recomputed as the event-weighted mean of `zone_outcome_summary` by the disrupted team: Atlético's 73.8% reproduces exactly, Barca's comes to 63.0% against a stated 62.4%. Close enough to be confident in the keying, but the small residual on Barca might be worth a look.

Separately, `duration_sec` on the notable pressure events diverges substantially from the frame span (event 53: 1,058 frames ≈ 42.3s wall clock, 8.6s duration). Assumed stoppage exclusion; no wall-clock spans are cited anywhere in the report.
