# Expected Net Yards at Pass Release

This Python model estimates final offensive net yardage before penalties, using only information available at the pass-release frame and the snap. It is an outcome-model component for the proposed Invisible Assist project, not a completed attention-attribution system or a reproduction of NFL Ghosts/RFCDE. It compares a training-mean baseline, a game-context baseline, and a tracking-feature gradient-boosting model on held-out games. Evaluation uses weeks 1-6 for fitting, week 7 for model selection, and week 8 for a single final test after refitting on weeks 1-7. It estimates associations for eligible pass attempts, not the causal yardage contribution of a player, and its limitations and measured results are documented in MODEL_CARD.md.

## Quick start

Use Python 3.11 or 3.12 and the exact dependency versions in requirements.txt. The original dataset ZIP remains separate; it is not bundled again.

```bash
python -m pip install -r requirements.txt
python predict.py --features results/example_features.csv --out predictions.csv
```

The model is already trained. The example contains held-out week-8 feature rows without outcome labels. Output `expected_net_yards` is the predicted conditional mean in yards; it is not a probability and need not be an integer.

To reproduce feature extraction, training and evaluation:

```bash
python train.py --data /path/to/nfl-big-data-bowl-regional-event-data-main.zip --out results
```

## Python integration

```python
import pandas as pd
from predict import predict_expected_yards

features = pd.read_csv('results/example_features.csv')
expected_yards = predict_expected_yards(features)
```

`train.feature_row` constructs features for a play from snap/release tracking frames, play metadata, a player-position mapping, and elapsed seconds. All attacking WR/TE/RB are represented, including blockers; no eventual target or completion label is used. Receiver slots are ordered by normalized depth, then lateral position, so they do not refer to fixed player identities. When constructing a single feature row, align it to `results/feature_columns.json` with `DataFrame.reindex(columns=columns)` to represent absent optional slots as missing values. Do not use this release-time model at arbitrary earlier frames without retraining and evaluation at those times.

## Contents

- `train.py`: data extraction, feature building, temporal model selection and test evaluation.
- `predict.py`: inference API and command-line utility.
- `results/tracking_model.joblib`: evaluated tracking model, preprocessing and metadata.
- `results/context_baseline.joblib`: evaluated context-only comparison model.
- `results/metrics.json`: validation and test metrics, exclusions, and clustered uncertainty.
- `results/features.csv`: one row per included play, with week and target for reproducibility.
- `results/example_features.csv`: outcome-free held-out inputs for inference.
- `results/test_predictions.csv`: actual and predicted yards for held-out week 8.
- `MODEL_CARD.md`: population, results, interpretation and limitations.

Only load joblib files from trusted sources. For a public competition submission, retain source attribution and separately follow the event rules regarding original work and permitted reuse.

## Sources

- Supplied regional event data and data dictionary: https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data
- Estimator documentation: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html
- Related motivation, not reused code or a reproduced model: https://arxiv.org/abs/2406.17220
