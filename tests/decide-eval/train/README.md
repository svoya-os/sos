# Fine-tuning Laya on Jackson's commands

Laya's multilingual checkpoint (Apache-2.0) fine-tuned with Laya's own recipe (RLCD, then a
calibration temperature), on a CPU:

- `base.py` — how people ask for each command of `jackson/fastpath.py` (`DECIDABLE`) and requests
  that are not one of them, Russian and English. None of them is taken from `../phrases.tsv`, which
  stays the held-out test (`train.py` drops any phrase that also appears there);
- `train.py` — builds the questions exactly as `../eval.py` asks them, adds fillers around the
  phrases («Джексон, …», «… пожалуйста»), trains, fits the temperature and saves the model.

`.github/workflows/laya-finetune.yml` runs both on a GitHub runner (1–2 hours without a GPU),
measures the model on `../phrases.tsv` and keeps it as a workflow artifact for a week; the report
lands in the `ci-screens` branch (`evals/decide-ft/<run>/`).

    python3 tests/decide-eval/train/train.py --dry-run      # the training set only

## Runs

| run | targets | held-out: picked right | acted right | wrong | ms p50 |
|---|---|---|---|---|---|
| zero-shot (no fine-tune) | — | 61% | 40/88 | 3 | 422 |
| [36241333457](https://github.com/svoya-os/sos/tree/ci-screens/evals/decide-ft/36241333457) | 0.9 on the right option | 94% | 17/88 | 0 | 234 |

The first fine-tune picks as well as the local chat model (95%, 13 s per decision) in a quarter
of a second, but it learnt to say «0.9» about everything: on new phrases every answer, right or
wrong, came out near 0.72, below Jackson's thresholds (0.8 to read, 0.9 to change something).
The next run trains toward 0.98 and fits the temperature on the right answers, not on the soft
targets; `TRAINING.json` then reports how many calibration phrases clear each threshold.
