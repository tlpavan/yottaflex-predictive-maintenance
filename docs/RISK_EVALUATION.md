# Historical Risk Evaluation

## Evaluation methodology

- Decision frequency: once per UTC day.
- Feature window: 24 hours.
- Prediction horizon: next 24 hours.
- Target: a machine failure occurring strictly after the decision time and within the prediction horizon.
- Maintenance history: only work orders opened by the decision timestamp are included.
- Failure events are used only to determine evaluation outcomes, never as scoring features.
- The final telemetry day is excluded because its future 24-hour outcome window is unavailable.

## Results

| Threshold | TP | FP | TN | FN | Precision | Recall | F1 | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| HIGH_OR_CRITICAL | 23 | 126 | 8625 | 126 | 0.1544 | 0.1544 | 0.1544 | 0.9717 |
| MEDIUM_OR_HIGH_OR_CRITICAL | 99 | 4771 | 3980 | 50 | 0.0203 | 0.6644 | 0.0395 | 0.4583 |

- Evaluation samples: 8900.
- Positive outcomes: 149.

## Limitations

- This is a backtest against synthetic generated failures, not real industrial failure data.
- Risk scores are heuristic decision-support scores, not calibrated probabilities.
- Results depend on the selected 24-hour prediction horizon and risk thresholds.
- The evaluation does not establish performance on independent real-world data.

## Chronological Holdout Evaluation

To check performance on later dates, the data was divided chronologically rather than randomly.

- Training period: 2026-07-01 to 2026-08-30.
- Training samples: 6,100.
- Training positive outcomes: 103.
- August 31 was excluded between the periods.
- Testing period: 2026-09-01 to 2026-09-27.
- Testing samples: 2,700.
- Testing positive outcomes: 45.
- The HIGH/CRITICAL threshold of 55 was selected using the training period F1-score.

### Holdout Results

| Metric | Result |
|---|---:|
| Threshold | 55 |
| True positives | 9 |
| False positives | 29 |
| True negatives | 2,626 |
| False negatives | 36 |
| Precision | 23.68% |
| Recall | 20.00% |
| F1-score | 21.69% |
| False-positive rate | 1.09% |

The holdout results show that the scoring approach identifies some future failures, but it misses many of them. The results are based on synthetic data and should not be treated as proof of real-world predictive performance.

The full-period results and chronological holdout results are separate evaluations and should not be combined.
