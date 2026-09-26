# Jackson's decision step: which command did the user mean?

109 phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: what Jackson would run — a fast-path pattern first, else the decider at his thresholds (p ≥ 0.9 to change something, 0.8 to read), commands only; *wrong*: a command the decider ran that nobody asked for (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.

| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |
|---|---|---|---|---|---|---|---|---|
| laya fine-tuned (multilingual) | ru | 74 | 93% | 56/60 | 1 | 13/14 | 419 / 432 | 0 |
| laya fine-tuned (multilingual) | en | 35 | 94% | 23/28 | 2 | 6/7 | 354 / 363 | 0 |
| laya fine-tuned (multilingual) | all | 109 | 94% | 79/88 | 3 | 19/21 | 418 / 430 | 0 |

## Misses

- laya fine-tuned (multilingual) · ru · «добавь звука»: expected volume_up, picked unmute (p 0.35), did none
- laya fine-tuned (multilingual) · ru · «слишком громко, приглуши»: expected volume_down, picked volume_down (p 0.87), did none
- laya fine-tuned (multilingual) · ru · «снова хочу слышать звук»: expected unmute, picked none (p 0.70), did none
- laya fine-tuned (multilingual) · ru · «батарейка скоро сядет?»: expected battery, picked battery (p 0.69), did none
- laya fine-tuned (multilingual) · ru · «поставь экран на весь размер»: expected none, picked brightness_up (p 0.93), did brightness_up
- laya fine-tuned (multilingual) · ru · «сколько стоит новая батарея для ноутбука»: expected none, picked battery (p 0.78), did none
- laya fine-tuned (multilingual) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.70), did none
- laya fine-tuned (multilingual) · en · «turn the sound down, the neighbors complain»: expected volume_down, picked volume_down (p 0.86), did none
- laya fine-tuned (multilingual) · en · «silence the speakers»: expected mute, picked mute (p 0.89), did none
- laya fine-tuned (multilingual) · en · «the screen is blinding me, dim it»: expected brightness_down, picked brightness_down (p 0.81), did none
- laya fine-tuned (multilingual) · en · «darker screen please»: expected brightness_down, picked brightness_up (p 0.90), did brightness_up
- laya fine-tuned (multilingual) · en · «enable bluetooth, I want my headphones»: expected bluetooth_on, picked bluetooth_on (p 0.77), did none
- laya fine-tuned (multilingual) · en · «time to eat, order a pizza»: expected none, picked time (p 0.90), did time
