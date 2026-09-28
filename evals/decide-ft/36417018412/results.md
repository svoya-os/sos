# Jackson's decision step: which command did the user mean?

109 phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: what Jackson would run — a fast-path pattern first, else the decider at his thresholds (p ≥ 0.9 to change something, 0.8 to read), commands only; *wrong*: a command the decider ran that nobody asked for (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.

| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |
|---|---|---|---|---|---|---|---|---|
| laya fine-tuned (multilingual) | ru | 74 | 97% | 55/60 | 0 | 14/14 | 417 / 429 | 0 |
| laya fine-tuned (multilingual) | en | 35 | 100% | 26/28 | 0 | 7/7 | 350 / 362 | 0 |
| laya fine-tuned (multilingual) | all | 109 | 98% | 81/88 | 0 | 21/21 | 414 / 427 | 0 |

## Misses

- laya fine-tuned (multilingual) · ru · «сделай тишину, совсем без звука»: expected mute, picked mute (p 0.78), did none
- laya fine-tuned (multilingual) · ru · «снова хочу слышать звук»: expected unmute, picked unmute (p 0.89), did none
- laya fine-tuned (multilingual) · ru · «можно экран посветлее»: expected brightness_up, picked brightness_up (p 0.90), did none
- laya fine-tuned (multilingual) · ru · «глаза режет, притуши экран»: expected brightness_down, picked brightness_down (p 0.79), did none
- laya fine-tuned (multilingual) · ru · «батарейка скоро сядет?»: expected battery, picked none (p 0.93), did none
- laya fine-tuned (multilingual) · ru · «поставь экран на весь размер»: expected none, picked brightness_up (p 0.67), did none
- laya fine-tuned (multilingual) · en · «silence the speakers»: expected mute, picked mute (p 0.90), did none
- laya fine-tuned (multilingual) · en · «enable bluetooth, I want my headphones»: expected bluetooth_on, picked bluetooth_on (p 0.51), did none
