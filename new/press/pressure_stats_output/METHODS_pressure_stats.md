# Pressure statistics: how the numbers were produced (generated 2026-10-03)

**Data.** Player and ball tracking from broadcast video of the first half (46.7 min at 25 fps), pitch coordinates in metres.
Possession comes from the provided possession flag; a change of possession counts only after a stable hold; stoppages are excluded.

**Build-up.** A build-up starts when a team has the ball in its own or middle third (thirds at 35 m and 70 m from its own goal) and ends in
success (ball held in the final third for at least 0.5 s), loss (the opponent gets a stable hold) or undecided (out of play, stoppage, untracked gap).

**Pressure on the ball carrier.** For every possession frame the press target is the carrier (else the ball). A defender presses when he is within 5.0 m of the target and either within
2.0 m or closing in at 1.5 m/s or more (measured over 0.5 s). The team is "under pressure" when at least one defender presses for 0.4 s in a row.

**Pressure episodes.** An episode starts with sustained pressure, continues while a defender is within 7.0 m of the pressed player, bridges interruptions of up to 0.5 s and lasts at least 0.5 s.
Counts are sensitive to this choice; the sensitivity table shows the alternatives.

**Statistics.** Shares and rates come with 95% intervals from resampling whole possession spells (frame-based figures) or build-ups (effect figures); proportions of build-ups use Wilson intervals.
The effect of pressure is the difference in the chance of losing the ball within 2 s of a moment (one moment per second), pressed vs not pressed in the previous second, plus logistic models adjusted for team, ball height, carrier share and open passing lanes.

**Limits.** (1) First half only, one match; tracking comes from broadcast video, so on average about one outfield player per team is not tracked in a frame: all pressure figures are lower bounds. (2) About half of the possession frames have no tracked carrier; there the press target is the ball position, and pressure on a loose or airborne ball is less well defined. Carrier-only figures are given where it matters. (3) Pressure is a geometric proxy (distance and closing speed of defenders); it does not use body orientation or intent. Episodes include sustained single-defender pressure and have not yet been validated against video (see the validation sample). (4) Player positions are inferred from average locations and checked by hand; they are not official line-up data. (5) Intervals are 95% intervals from resampling possession spells or build-ups; with about 90 build-ups per team, differences with overlapping intervals should not be presented as real. (6) The effect estimates are associations (pressed vs not pressed within a build-up), adjusted for a few covariates; they are not causal.
