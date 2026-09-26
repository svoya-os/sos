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
