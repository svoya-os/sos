# Jackson's decision step: which command did the user mean?

109 phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: what Jackson would run — a fast-path pattern first, else the decider at his thresholds (p ≥ 0.9 to change something, 0.8 to read), commands only; *wrong*: a command the decider ran that nobody asked for (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.

| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |
|---|---|---|---|---|---|---|---|---|
| laya fine-tuned (multilingual) | ru | 74 | 95% | 10/60 | 0 | 14/14 | 236 / 241 | 0 |
| laya fine-tuned (multilingual) | en | 35 | 94% | 7/28 | 0 | 7/7 | 203 / 211 | 0 |
| laya fine-tuned (multilingual) | all | 109 | 94% | 17/88 | 0 | 21/21 | 234 / 240 | 0 |

## Misses

- laya fine-tuned (multilingual) · ru · «слушай, сделай-ка погромче, ничего не слышно»: expected volume_up, picked volume_up (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «добавь звука»: expected volume_up, picked volume_up (p 0.55), did none
- laya fine-tuned (multilingual) · ru · «звук тихий, прибавь»: expected volume_up, picked volume_up (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «можно чуть громче музыку»: expected volume_up, picked volume_up (p 0.54), did none
- laya fine-tuned (multilingual) · ru · «не слышу ничего, сделай громче»: expected volume_up, picked volume_up (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «слушай, сделай-ка потише, соседи жалуются»: expected volume_down, picked volume_down (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «слишком громко, приглуши»: expected volume_down, picked volume_down (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «звук поменьше сделай»: expected volume_down, picked volume_down (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «чуть потише можно»: expected volume_down, picked volume_down (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «тише давай, уши болят»: expected volume_down, picked volume_down (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «выруби звук совсем»: expected mute, picked mute (p 0.71), did none
- laya fine-tuned (multilingual) · ru · «отключи звук полностью»: expected mute, picked mute (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «сделай тишину, совсем без звука»: expected mute, picked mute (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «звук в ноль и выключи»: expected mute, picked mute (p 0.71), did none
- laya fine-tuned (multilingual) · ru · «включи звук обратно»: expected unmute, picked unmute (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «звук снова включи пожалуйста»: expected unmute, picked unmute (p 0.71), did none
- laya fine-tuned (multilingual) · ru · «снова хочу слышать звук»: expected unmute, picked unmute (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «экран тусклый, сделай поярче»: expected brightness_up, picked brightness_up (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «прибавь яркости»: expected brightness_up, picked brightness_up (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «ярче экран пожалуйста»: expected brightness_up, picked brightness_up (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «на экране ничего не видно, яркость выше»: expected brightness_up, picked brightness_up (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «можно экран посветлее»: expected brightness_up, picked brightness_down (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «экран слепит, убавь яркость»: expected brightness_down, picked brightness_down (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «потемнее экран сделай»: expected brightness_down, picked brightness_down (p 0.71), did none
- laya fine-tuned (multilingual) · ru · «яркость поменьше»: expected brightness_down, picked brightness_down (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «глаза режет, притуши экран»: expected brightness_down, picked brightness_down (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «сделай экран темнее на ночь»: expected brightness_down, picked brightness_down (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «врубай вай-фай»: expected wifi_on, picked wifi_on (p 0.76), did none
- laya fine-tuned (multilingual) · ru · «мне нужен вайфай, включи»: expected wifi_on, picked wifi_on (p 0.75), did none
- laya fine-tuned (multilingual) · ru · «включи беспроводной интернет»: expected wifi_on, picked wifi_on (p 0.70), did none
- laya fine-tuned (multilingual) · ru · «вырубай вай фай»: expected wifi_off, picked wifi_off (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «вайфай не нужен, отключай»: expected wifi_off, picked wifi_off (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «отруби беспроводной интернет»: expected wifi_off, picked wifi_off (p 0.66), did none
- laya fine-tuned (multilingual) · ru · «врубай блютус, наушники подключу»: expected bluetooth_on, picked bluetooth_on (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «bluetooth включи пожалуйста»: expected bluetooth_on, picked bluetooth_on (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «блютус больше не нужен, выруби»: expected bluetooth_off, picked bluetooth_off (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «вырубай bluetooth»: expected bluetooth_off, picked bluetooth_off (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «заблокируй экран, я отойду»: expected lock, picked lock (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «блокни комп»: expected lock, picked lock (p 0.68), did none
- laya fine-tuned (multilingual) · ru · «поставь блокировку экрана»: expected lock, picked lock (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «я ушёл, заблокируй»: expected lock, picked lock (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «щёлкни снимок экрана»: expected screenshot, picked screenshot (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «заскринь экран»: expected screenshot, picked screenshot (p 0.70), did none
- laya fine-tuned (multilingual) · ru · «сохрани скриншот»: expected screenshot, picked screenshot (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «сколько там заряда?»: expected battery, picked battery (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «батарейка скоро сядет?»: expected battery, picked none (p 0.68), did none
- laya fine-tuned (multilingual) · ru · «проверь заряд»: expected battery, picked battery (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «какой уровень батареи»: expected battery, picked battery (p 0.73), did none
- laya fine-tuned (multilingual) · ru · «подскажи время»: expected time, picked time (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «сколько времени уже?»: expected time, picked time (p 0.72), did none
- laya fine-tuned (multilingual) · ru · «поставь экран на весь размер»: expected none, picked brightness_up (p 0.74), did none
- laya fine-tuned (multilingual) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.43), did none
- laya fine-tuned (multilingual) · en · «crank it up a bit, I can barely hear»: expected volume_up, picked volume_up (p 0.75), did none
- laya fine-tuned (multilingual) · en · «bump the sound up»: expected volume_up, picked volume_up (p 0.72), did none
- laya fine-tuned (multilingual) · en · «too loud, bring it down»: expected volume_down, picked volume_down (p 0.72), did none
- laya fine-tuned (multilingual) · en · «turn the sound down, the neighbors complain»: expected volume_down, picked volume_down (p 0.64), did none
- laya fine-tuned (multilingual) · en · «kill the sound completely»: expected mute, picked mute (p 0.71), did none
- laya fine-tuned (multilingual) · en · «silence the speakers»: expected mute, picked mute (p 0.68), did none
- laya fine-tuned (multilingual) · en · «bring the sound back»: expected unmute, picked unmute (p 0.73), did none
- laya fine-tuned (multilingual) · en · «turn the sound back on»: expected unmute, picked unmute (p 0.70), did none
- laya fine-tuned (multilingual) · en · «the screen is too dim, brighten it»: expected brightness_up, picked brightness_up (p 0.73), did none
- laya fine-tuned (multilingual) · en · «more brightness please»: expected brightness_up, picked brightness_up (p 0.71), did none
- laya fine-tuned (multilingual) · en · «the screen is blinding me, dim it»: expected brightness_down, picked brightness_down (p 0.73), did none
- laya fine-tuned (multilingual) · en · «darker screen please»: expected brightness_down, picked brightness_up (p 0.72), did none
- laya fine-tuned (multilingual) · en · «switch the wifi on»: expected wifi_on, picked wifi_on (p 0.72), did none
- laya fine-tuned (multilingual) · en · «kill the wifi»: expected wifi_off, picked wifi_off (p 0.75), did none
- laya fine-tuned (multilingual) · en · «enable bluetooth, I want my headphones»: expected bluetooth_on, picked bluetooth_on (p 0.67), did none
- laya fine-tuned (multilingual) · en · «switch bluetooth off»: expected bluetooth_off, picked bluetooth_off (p 0.70), did none
- laya fine-tuned (multilingual) · en · «lock the screen, I'm stepping away»: expected lock, picked lock (p 0.71), did none
- laya fine-tuned (multilingual) · en · «lock it up»: expected lock, picked lock (p 0.58), did none
- laya fine-tuned (multilingual) · en · «grab a screenshot»: expected screenshot, picked screenshot (p 0.70), did none
- laya fine-tuned (multilingual) · en · «how much charge is left?»: expected battery, picked battery (p 0.72), did none
- laya fine-tuned (multilingual) · en · «check the battery»: expected battery, picked battery (p 0.72), did none
- laya fine-tuned (multilingual) · en · «time to eat, order a pizza»: expected none, picked time (p 0.55), did none
