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
| [36249658179](https://github.com/svoya-os/sos/tree/ci-screens/evals/decide-ft/36249658179) | 0.98, temperature fitted on the answers | 94% | 79/88 | 3 | 418 |

The first fine-tune picks as well as the local chat model (95%, 13 s per decision) in a quarter
of a second, but it learnt to say «0.9» about everything: on new phrases every answer, right or
wrong, came out near 0.72, below Jackson's thresholds (0.8 to read, 0.9 to change something).
The second run trains toward 0.98 and fits the temperature on the right answers: calibrated
(ECE 0.019 on the calibration slice), 79 of 88 commands acted — but 3 wrong actions («darker
screen please» as brighter, a full-screen window, «time to eat» as the time), where the local chat
model has none. At 0.94 to change something and 0.9 to read, Laya would act on 59 of 88 with none
wrong (thresholds chosen on these same phrases). The third run adds English phrasings (the thinnest
lists) and requests that name the screen, sound, time or battery without asking for a command.
The chat model (jackson/decide.py): 95% picked, 84/88 acted, 0 wrong, 13 s per decision on a CPU.
