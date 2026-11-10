# Published example artifacts

These small artifacts support the README, offline JavaScript checks, and application startup. The full upstream NFL/PFF dataset is downloaded separately and excluded from Git.

| Artifact | Contents |
| --- | --- |
| `core_fixture.json` | Two pre-release example excerpts: game 2021101700 / play 1621 and game 2021090900 / play 137. Includes observed coordinates, player metadata, and Python reference attention weights for the actual receiver. These test both offensive directions. |
| `results/receiver_cohort.csv` | Lightweight index for 4,465 eligible completed-pass plays: actual receiver, observation endpoints, and a preferred alternative-route player. Full frame data is still read from the downloaded dataset. |
| `results/trend_report.json` | Cohort coverage, exclusions, pattern counts, duration strata, and nine sensitivity settings. |
| `results/last_decline_report.json` | Coverage and summary of attribution during the last significant declining leg. |
| `results/play_1621_last_decline.json` | Detailed example interval, teammate scores, and positive defender-level contributions. |
| `results/catch_validation.csv` | The 21 original nearest-offensive-player labels from available catch events. This is a heuristic cross-check snapshot, not ground truth. One label (2021090900 / 3909) conflicts with the receiver named in the play description and is excluded from the main cohort. |

The examples are derived from the [regional-event source dataset](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data), with tracking from NFL Next Gen Stats and scouting from Pro Football Focus. Names, positions, and trajectories retain that provenance. They are not synthetic model observations.

Regenerating full analyses requires the original CSV files. `tools/generate_figures.py` and `tools/verify_core.mjs` can use these committed artifacts without the full dataset. The plotted values and published findings reflect this specific 2021 snapshot and the documented heuristic model.
