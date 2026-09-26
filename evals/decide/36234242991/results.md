# Jackson's decision step: which command did the user mean?

109 phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: what Jackson would run at his thresholds (p ≥ 0.9 to change something, 0.8 to read), commands only; *wrong*: an action other than the expected one (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.

| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |
|---|---|---|---|---|---|---|---|---|
| laya (convaiinnovations/laya/multilingual) | ru | 74 | 58% | 16/60 | 3 | 11/14 | 288 / 302 | 0 |
| laya (convaiinnovations/laya/multilingual) | en | 35 | 66% | 13/28 | 0 | 7/7 | 270 / 276 | 0 |
| laya (convaiinnovations/laya/multilingual) | all | 109 | 61% | 29/88 | 3 | 18/21 | 287 / 300 | 0 |

## Misses

- laya (convaiinnovations/laya/multilingual) · ru · «слушай, сделай-ка погромче, ничего не слышно»: expected volume_up, picked volume_up (p 0.49), did none
- laya (convaiinnovations/laya/multilingual) · ru · «добавь звука»: expected volume_up, picked volume_up (p 0.71), did none
- laya (convaiinnovations/laya/multilingual) · ru · «громкость повыше пожалуйста»: expected volume_up, picked volume_up (p 0.64), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук тихий, прибавь»: expected volume_up, picked volume_down (p 0.65), did none
- laya (convaiinnovations/laya/multilingual) · ru · «можно чуть громче музыку»: expected volume_up, picked volume_up (p 0.38), did none
- laya (convaiinnovations/laya/multilingual) · ru · «не слышу ничего, сделай громче»: expected volume_up, picked volume_up (p 0.83), did none
- laya (convaiinnovations/laya/multilingual) · ru · «слушай, сделай-ка потише, соседи жалуются»: expected volume_down, picked volume_down (p 0.37), did none
- laya (convaiinnovations/laya/multilingual) · ru · «убавь звук»: expected volume_down, picked volume_up (p 0.38), did none
- laya (convaiinnovations/laya/multilingual) · ru · «слишком громко, приглуши»: expected volume_down, picked volume_up (p 0.36), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук поменьше сделай»: expected volume_down, picked volume_down (p 0.26), did none
- laya (convaiinnovations/laya/multilingual) · ru · «чуть потише можно»: expected volume_down, picked battery (p 0.35), did none
- laya (convaiinnovations/laya/multilingual) · ru · «тише давай, уши болят»: expected volume_down, picked volume_down (p 0.73), did none
- laya (convaiinnovations/laya/multilingual) · ru · «выруби звук совсем»: expected mute, picked mute (p 0.55), did none
- laya (convaiinnovations/laya/multilingual) · ru · «отключи звук полностью»: expected mute, picked mute (p 0.67), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сделай тишину, совсем без звука»: expected mute, picked volume_down (p 0.69), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук в ноль и выключи»: expected mute, picked unmute (p 0.38), did none
- laya (convaiinnovations/laya/multilingual) · ru · «верни звук»: expected unmute, picked unmute (p 0.34), did none
- laya (convaiinnovations/laya/multilingual) · ru · «экран тусклый, сделай поярче»: expected brightness_up, picked brightness_up (p 0.61), did none
- laya (convaiinnovations/laya/multilingual) · ru · «прибавь яркости»: expected brightness_up, picked brightness_up (p 0.78), did none
- laya (convaiinnovations/laya/multilingual) · ru · «ярче экран пожалуйста»: expected brightness_up, picked brightness_up (p 0.81), did none
- laya (convaiinnovations/laya/multilingual) · ru · «на экране ничего не видно, яркость выше»: expected brightness_up, picked brightness_up (p 0.51), did none
- laya (convaiinnovations/laya/multilingual) · ru · «можно экран посветлее»: expected brightness_up, picked battery (p 0.46), did none
- laya (convaiinnovations/laya/multilingual) · ru · «экран слепит, убавь яркость»: expected brightness_down, picked brightness_up (p 0.67), did none
- laya (convaiinnovations/laya/multilingual) · ru · «потемнее экран сделай»: expected brightness_down, picked brightness_down (p 0.57), did none
- laya (convaiinnovations/laya/multilingual) · ru · «яркость поменьше»: expected brightness_down, picked brightness_up (p 0.57), did none
- laya (convaiinnovations/laya/multilingual) · ru · «глаза режет, притуши экран»: expected brightness_down, picked battery (p 0.46), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сделай экран темнее на ночь»: expected brightness_down, picked brightness_down (p 0.65), did none
- laya (convaiinnovations/laya/multilingual) · ru · «врубай вай-фай»: expected wifi_on, picked none (p 0.33), did none
- laya (convaiinnovations/laya/multilingual) · ru · «подключи wi-fi»: expected wifi_on, picked wifi_on (p 0.98), did none
- laya (convaiinnovations/laya/multilingual) · ru · «мне нужен вайфай, включи»: expected wifi_on, picked wifi_on (p 0.49), did none
- laya (convaiinnovations/laya/multilingual) · ru · «включи беспроводной интернет»: expected wifi_on, picked wifi_on (p 0.66), did none
- laya (convaiinnovations/laya/multilingual) · ru · «вырубай вай фай»: expected wifi_off, picked battery (p 0.34), did none
- laya (convaiinnovations/laya/multilingual) · ru · «отключи wi-fi»: expected wifi_off, picked wifi_off (p 1.00), did none
- laya (convaiinnovations/laya/multilingual) · ru · «вайфай не нужен, отключай»: expected wifi_off, picked wifi_on (p 0.63), did none
- laya (convaiinnovations/laya/multilingual) · ru · «отруби беспроводной интернет»: expected wifi_off, picked battery (p 0.55), did none
- laya (convaiinnovations/laya/multilingual) · ru · «включи блютуз»: expected bluetooth_on, picked volume_up (p 0.56), did none
- laya (convaiinnovations/laya/multilingual) · ru · «врубай блютус, наушники подключу»: expected bluetooth_on, picked bluetooth_on (p 0.32), did none
- laya (convaiinnovations/laya/multilingual) · ru · «отключи блютуз»: expected bluetooth_off, picked volume_down (p 0.38), did none
- laya (convaiinnovations/laya/multilingual) · ru · «блютус больше не нужен, выруби»: expected bluetooth_off, picked volume_down (p 0.24), did none
- laya (convaiinnovations/laya/multilingual) · ru · «блокни комп»: expected lock, picked battery (p 0.33), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сделай скрин»: expected screenshot, picked screenshot (p 0.38), did none
- laya (convaiinnovations/laya/multilingual) · ru · «щёлкни снимок экрана»: expected screenshot, picked screenshot (p 0.56), did none
- laya (convaiinnovations/laya/multilingual) · ru · «заскринь экран»: expected screenshot, picked brightness_up (p 0.80), did none
- laya (convaiinnovations/laya/multilingual) · ru · «который час?»: expected time, picked time (p 0.45), did none
- laya (convaiinnovations/laya/multilingual) · ru · «включи музыку»: expected none, picked wifi_on (p 0.43), did none
- laya (convaiinnovations/laya/multilingual) · ru · «поставь экран на весь размер»: expected none, picked brightness_up (p 0.65), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сколько стоит новая батарея для ноутбука»: expected none, picked battery (p 1.00), did battery
- laya (convaiinnovations/laya/multilingual) · ru · «сколько времени займёт установка»: expected none, picked time (p 0.90), did time
- laya (convaiinnovations/laya/multilingual) · ru · «время обеда, закажи пиццу»: expected none, picked battery (p 0.39), did none
- laya (convaiinnovations/laya/multilingual) · ru · «открой настройки звука»: expected none, picked volume_up (p 0.60), did none
- laya (convaiinnovations/laya/multilingual) · ru · «запиши видео с экрана»: expected none, picked screenshot (p 0.87), did none
- laya (convaiinnovations/laya/multilingual) · ru · «блокнот открой»: expected none, picked battery (p 0.22), did none
- laya (convaiinnovations/laya/multilingual) · ru · «расскажи про яркость звёзд»: expected none, picked brightness_up (p 0.58), did none
- laya (convaiinnovations/laya/multilingual) · ru · «экран моргает, что делать»: expected none, picked brightness_up (p 0.22), did none
- laya (convaiinnovations/laya/multilingual) · ru · «интернет медленный, проверь скорость»: expected none, picked battery (p 0.59), did none
- laya (convaiinnovations/laya/multilingual) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.95), did screenshot
- laya (convaiinnovations/laya/multilingual) · en · «crank it up a bit, I can barely hear»: expected volume_up, picked volume_up (p 0.63), did none
- laya (convaiinnovations/laya/multilingual) · en · «louder please»: expected volume_up, picked volume_up (p 0.48), did none
- laya (convaiinnovations/laya/multilingual) · en · «bump the sound up»: expected volume_up, picked brightness_up (p 0.73), did none
- laya (convaiinnovations/laya/multilingual) · en · «too loud, bring it down»: expected volume_down, picked volume_up (p 0.42), did none
- laya (convaiinnovations/laya/multilingual) · en · «quieter please»: expected volume_down, picked volume_down (p 0.59), did none
- laya (convaiinnovations/laya/multilingual) · en · «turn the sound down, the neighbors complain»: expected volume_down, picked none (p 0.60), did none
- laya (convaiinnovations/laya/multilingual) · en · «kill the sound completely»: expected mute, picked mute (p 0.78), did none
- laya (convaiinnovations/laya/multilingual) · en · «silence the speakers»: expected mute, picked volume_down (p 0.50), did none
- laya (convaiinnovations/laya/multilingual) · en · «bring the sound back»: expected unmute, picked unmute (p 0.21), did none
- laya (convaiinnovations/laya/multilingual) · en · «turn the sound back on»: expected unmute, picked volume_down (p 0.26), did none
- laya (convaiinnovations/laya/multilingual) · en · «the screen is blinding me, dim it»: expected brightness_down, picked lock (p 0.59), did none
- laya (convaiinnovations/laya/multilingual) · en · «darker screen please»: expected brightness_down, picked brightness_up (p 0.56), did none
- laya (convaiinnovations/laya/multilingual) · en · «enable wi-fi please»: expected wifi_on, picked wifi_on (p 1.00), did none
- laya (convaiinnovations/laya/multilingual) · en · «disable wi-fi»: expected wifi_off, picked wifi_off (p 1.00), did none
- laya (convaiinnovations/laya/multilingual) · en · «time please»: expected time, picked time (p 0.56), did none
- laya (convaiinnovations/laya/multilingual) · en · «why is my wifi so slow?»: expected none, picked wifi_on (p 0.49), did none
- laya (convaiinnovations/laya/multilingual) · en · «open the sound settings»: expected none, picked volume_up (p 0.29), did none
- laya (convaiinnovations/laya/multilingual) · en · «record a video of the screen»: expected none, picked screenshot (p 0.81), did none
- laya (convaiinnovations/laya/multilingual) · en · «time to eat, order a pizza»: expected none, picked time (p 0.63), did none
- laya (convaiinnovations/laya/multilingual) · en · «my screen flickers, what should I do»: expected none, picked lock (p 0.72), did none
