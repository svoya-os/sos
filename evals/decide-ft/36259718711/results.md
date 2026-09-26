# Jackson's decision step: which command did the user mean?

109 phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: what Jackson would run — a fast-path pattern first, else the decider at his thresholds (p ≥ 0.9 to change something, 0.8 to read), commands only; *wrong*: a command the decider ran that nobody asked for (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.

| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |
|---|---|---|---|---|---|---|---|---|
| laya fine-tuned (multilingual) | ru | 74 | 97% | 56/60 | 0 | 14/14 | 486 / 496 | 0 |
| laya fine-tuned (multilingual) | en | 35 | 100% | 25/28 | 0 | 7/7 | 410 / 425 | 0 |
| laya fine-tuned (multilingual) | all | 109 | 98% | 81/88 | 0 | 21/21 | 483 / 496 | 0 |

## Misses

- laya fine-tuned (multilingual) · ru · «слушай, сделай-ка погромче, ничего не слышно»: expected volume_up, picked volume_up (p 0.89), did none
- laya fine-tuned (multilingual) · ru · «сделай тишину, совсем без звука»: expected mute, picked mute (p 0.89), did none
- laya fine-tuned (multilingual) · ru · «заскринь экран»: expected screenshot, picked screenshot (p 0.89), did none
- laya fine-tuned (multilingual) · ru · «батарейка скоро сядет?»: expected battery, picked battery (p 0.71), did none
- laya fine-tuned (multilingual) · ru · «сколько стоит новая батарея для ноутбука»: expected none, picked battery (p 0.82), did none
- laya fine-tuned (multilingual) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.69), did none
- laya fine-tuned (multilingual) · en · «silence the speakers»: expected mute, picked mute (p 0.71), did none
- laya fine-tuned (multilingual) · en · «darker screen please»: expected brightness_down, picked brightness_down (p 0.88), did none
- laya fine-tuned (multilingual) · en · «enable bluetooth, I want my headphones»: expected bluetooth_on, picked bluetooth_on (p 0.89), did none
