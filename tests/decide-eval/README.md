# Jackson's decision step: an evaluation

A short request that sounds like a system command but matches none of the fast-path patterns
(«слушай, сделай-ка потише, соседи жалуются») goes to a *decider*: it picks one of the commands in
`jackson/fastpath.py` (`DECIDABLE`) or «none of these», with a probability. Jackson runs the command
only when the decider is sure (p ≥ 0.9 for commands that change something, 0.8 for read-only ones).

`eval.py` measures deciders on `phrases.tsv` (Russian and English, commands and non-commands):

- **llm** — what SOS uses today: one token from the local chat model with log-probabilities
  (`jackson/decide.py`, Qwen3.5 4B on llama.cpp in CI);
- **laya** — [Laya](https://huggingface.co/convaiinnovations/laya), an open (Apache-2.0)
  non-generative decision model, the multilingual checkpoint.

The workflow `.github/workflows/decide-eval.yml` runs both on a GitHub runner's CPU whenever this
folder changes and publishes `results.md` to the `ci-screens` branch (`evals/decide/<run>/`).

Local run against a llama.cpp server:

    python3 tests/decide-eval/eval.py --llm http://127.0.0.1:8080/v1 --out dist/eval

The number that matters is **wrong**: a command run that the user did not ask for.
