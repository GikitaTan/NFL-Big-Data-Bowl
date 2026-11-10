# Model card: expected net yards at pass release

## Target and population

Target: `prePenaltyPlayResult`, the dataset-defined final offensive net yards before penalties. This is total play yardage, not remaining yards from the release position, YAC, EPA, completion probability, or a player-specific causal effect. Negative target values are retained; predictions are not forced nonnegative.

Population: 2021 weeks 1-8, pass attempts with outcomes C/I/IN, an observed ball_snap and pass_forward, 11 observed players on each side at release, one roster-designated QB, and at least one WR/TE/RB. Plays with recorded foul names are excluded. Sacks, scrambles and non-pass attempts are outside scope. The eligibility rules narrow applicability to clean, standard pass attempts; they are not a filter for successful passes.

## Data and timing

One row per play. The only tracking snapshots are ball_snap and the first pass_forward frame; no post-release rows or ball-flight information enter the features. Elapsed time uses frame difference / 10 because the displayed timestamp may be rounded. Coordinates and velocity are rotated so the offense always moves toward increasing x. The release event is treated as retrospectively known; this is not a pre-snap or live pre-release forecaster.

Predictors include down, distance, quarter, field position, score difference, clock, personnel, formation, release timing, QB location/movement/pressure, and attacking skill-player geometry, speed, separation and nearest-defender velocity. Skill players are sorted by depth; individual identities, names, target labels and outcomes are excluded. No custom attention or transfer score has yet been added. No PFF outcome/coverage/route annotations are used as predictors. Personnel and formation come from supplied metadata and are assumed observable by release.

## Training and independent evaluation

HistGradientBoostingRegressor with squared-error loss estimates conditional mean yards. This is an implemented baseline, not RFCDE. Each feature set uses three prespecified configurations; selection minimizes week-7 RMSE, not MAE. After selection, fit on weeks 1-7 and evaluate once on week 8. Preprocessing is fit only on each training partition. Week 8 is not used for tuning or model selection. Do not repeatedly tune against this test set in subsequent development.

| Split | Plays | Games |
|---|---:|---:|
| train_weeks_1_6 | 5287 | 94 |
| validation_week_7 | 737 | 13 |
| test_week_8 | 843 | 15 |

| Test model | MAE (yards) | RMSE (yards) | R2 | Mean prediction minus actual |
|---|---:|---:|---:|---:|
| mean_baseline | 6.7231 | 9.1750 | -0.0064 | 0.7333 |
| context_baseline | 6.4976 | 8.9664 | 0.0388 | 0.7132 |
| tracking_model | 6.2807 | 8.7782 | 0.0787 | 0.4271 |

Tracking improves test RMSE by 0.1882 yards (2.10%) and MAE by 0.2169 yards. The paired 95% game-cluster bootstrap interval for RMSE improvement is [-0.0780, 0.4686] yards (1,000 resamples of the 15 test games). It includes zero: the modest improvement is not conclusive evidence of reliable superiority. This interval describes aggregate error improvement, not a prediction interval for a play.

R2 is low: most play-level variation remains unexplained. There is no observed target receiver or ball trajectory after release in the model, and outcomes depend on completion, execution and unobserved factors. Do not present the output as precise yardage, an attention-model validation, or proof of player value. NFL Ghosts models catch-time YAC under a different data design; its published accuracy is not transferable here.

## Integration with Invisible Assist

Use this as an outcome baseline. Evaluate added attention/transfer features out of sample, preferably with nested temporal evaluation or an additional untouched period. Shared distance predictors can produce mechanical correlations between attention and expected yards; comparing those two predictions alone is not validation. Arbitrarily removing or moving players may generate out-of-distribution states, so prediction differences must not be called causal yards created. Early-frame expected-yard trajectories require a separately trained and evaluated model for those times.

## Exclusions

```json
{
  "tracking_plays": 8557,
  "excluded_missing_event": 43,
  "excluded_penalty_play": 631,
  "excluded_not_pass_attempt": 992,
  "excluded_incomplete_or_unusual_personnel": 24,
  "included": 6867
}
```

## Verification

- Saved model reloaded and exactly reproduced held-out predictions (floating tolerance 1e-10).
- Features unique by gameId/playId and all split game sets disjoint.
- Predictor allowlist excludes labels, result descriptions, penalties, identifiers and week.
- Field reflection invariance passed on ten plays.
- No post-release frame selection in feature construction.

## Reproducibility

Exact dependency versions are pinned in requirements.txt. Random seed is 42. The original data ZIP is supplied separately; features.csv is included to inspect every modeled play. Training on the full ZIP can be reproduced with the README command. Original sources are linked in README.md.
