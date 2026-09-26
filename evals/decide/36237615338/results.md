# Jackson's decision step: which command did the user mean?

109 phrases (tests/decide-eval/phrases.tsv). *picked*: the decider's top option; *acted*: what Jackson would run — a fast-path pattern first, else the decider at his thresholds (p ≥ 0.9 to change something, 0.8 to read), commands only; *wrong*: a command the decider ran that nobody asked for (the number that must stay 0); *stayed out*: phrases that are not commands and ran nothing.

| decider | lang | n | picked right | acted right | wrong | stayed out | ms p50 / p95 | errors |
|---|---|---|---|---|---|---|---|---|
| laya (convaiinnovations/laya/multilingual) | ru | 74 | 59% | 22/60 | 2 | 12/14 | 416 / 431 | 0 |
| laya (convaiinnovations/laya/multilingual) | en | 35 | 63% | 18/28 | 1 | 7/7 | 348 / 360 | 0 |
| laya (convaiinnovations/laya/multilingual) | all | 109 | 61% | 40/88 | 3 | 19/21 | 414 / 429 | 0 |
| laya (Router: checkpoint by language) | ru | 74 | 59% | 22/60 | 2 | 12/14 | 416 / 429 | 0 |
| laya (Router: checkpoint by language) | en | 35 | 23% | 8/28 | 0 | 7/7 | 893 / 941 | 0 |
| laya (Router: checkpoint by language) | all | 109 | 48% | 30/88 | 2 | 19/21 | 419 / 919 | 0 |
| llm (jackson/decide.py) | ru | 74 | 95% | 56/60 | 2 | 12/14 | 13299 / 13567 | 0 |
| llm (jackson/decide.py) | en | 35 | 97% | 28/28 | 0 | 7/7 | 10514 / 10752 | 0 |
| llm (jackson/decide.py) | all | 109 | 95% | 84/88 | 2 | 19/21 | 13248 / 13529 | 0 |

## Misses

- laya (convaiinnovations/laya/multilingual) · ru · «слушай, сделай-ка погромче, ничего не слышно»: expected volume_up, picked volume_up (p 0.21), did none
- laya (convaiinnovations/laya/multilingual) · ru · «добавь звука»: expected volume_up, picked volume_up (p 0.26), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук тихий, прибавь»: expected volume_up, picked volume_down (p 0.50), did none
- laya (convaiinnovations/laya/multilingual) · ru · «можно чуть громче музыку»: expected volume_up, picked volume_up (p 0.28), did none
- laya (convaiinnovations/laya/multilingual) · ru · «не слышу ничего, сделай громче»: expected volume_up, picked volume_up (p 0.59), did none
- laya (convaiinnovations/laya/multilingual) · ru · «слушай, сделай-ка потише, соседи жалуются»: expected volume_down, picked battery (p 0.31), did none
- laya (convaiinnovations/laya/multilingual) · ru · «убавь звук»: expected volume_down, picked brightness_down (p 0.30), did volume_down
- laya (convaiinnovations/laya/multilingual) · ru · «слишком громко, приглуши»: expected volume_down, picked volume_up (p 0.58), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук поменьше сделай»: expected volume_down, picked battery (p 0.39), did none
- laya (convaiinnovations/laya/multilingual) · ru · «чуть потише можно»: expected volume_down, picked battery (p 0.34), did none
- laya (convaiinnovations/laya/multilingual) · ru · «тише давай, уши болят»: expected volume_down, picked volume_down (p 0.44), did none
- laya (convaiinnovations/laya/multilingual) · ru · «выруби звук совсем»: expected mute, picked mute (p 0.61), did none
- laya (convaiinnovations/laya/multilingual) · ru · «отключи звук полностью»: expected mute, picked mute (p 0.75), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сделай тишину, совсем без звука»: expected mute, picked volume_down (p 0.52), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук в ноль и выключи»: expected mute, picked battery (p 0.28), did none
- laya (convaiinnovations/laya/multilingual) · ru · «включи звук обратно»: expected unmute, picked battery (p 0.29), did none
- laya (convaiinnovations/laya/multilingual) · ru · «звук снова включи пожалуйста»: expected unmute, picked unmute (p 0.40), did none
- laya (convaiinnovations/laya/multilingual) · ru · «снова хочу слышать звук»: expected unmute, picked volume_up (p 0.24), did none
- laya (convaiinnovations/laya/multilingual) · ru · «экран тусклый, сделай поярче»: expected brightness_up, picked brightness_up (p 0.58), did none
- laya (convaiinnovations/laya/multilingual) · ru · «прибавь яркости»: expected brightness_up, picked brightness_up (p 0.90), did none
- laya (convaiinnovations/laya/multilingual) · ru · «ярче экран пожалуйста»: expected brightness_up, picked brightness_up (p 0.86), did none
- laya (convaiinnovations/laya/multilingual) · ru · «на экране ничего не видно, яркость выше»: expected brightness_up, picked brightness_up (p 0.35), did none
- laya (convaiinnovations/laya/multilingual) · ru · «можно экран посветлее»: expected brightness_up, picked battery (p 0.52), did none
- laya (convaiinnovations/laya/multilingual) · ru · «экран слепит, убавь яркость»: expected brightness_down, picked brightness_up (p 0.54), did none
- laya (convaiinnovations/laya/multilingual) · ru · «потемнее экран сделай»: expected brightness_down, picked brightness_down (p 0.48), did none
- laya (convaiinnovations/laya/multilingual) · ru · «яркость поменьше»: expected brightness_down, picked battery (p 0.50), did none
- laya (convaiinnovations/laya/multilingual) · ru · «глаза режет, притуши экран»: expected brightness_down, picked battery (p 0.60), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сделай экран темнее на ночь»: expected brightness_down, picked brightness_down (p 0.48), did none
- laya (convaiinnovations/laya/multilingual) · ru · «врубай вай-фай»: expected wifi_on, picked wifi_on (p 0.31), did none
- laya (convaiinnovations/laya/multilingual) · ru · «мне нужен вайфай, включи»: expected wifi_on, picked wifi_on (p 0.90), did none
- laya (convaiinnovations/laya/multilingual) · ru · «вырубай вай фай»: expected wifi_off, picked battery (p 0.70), did none
- laya (convaiinnovations/laya/multilingual) · ru · «вайфай не нужен, отключай»: expected wifi_off, picked wifi_off (p 0.70), did none
- laya (convaiinnovations/laya/multilingual) · ru · «отруби беспроводной интернет»: expected wifi_off, picked wifi_on (p 0.46), did none
- laya (convaiinnovations/laya/multilingual) · ru · «врубай блютус, наушники подключу»: expected bluetooth_on, picked bluetooth_on (p 0.77), did none
- laya (convaiinnovations/laya/multilingual) · ru · «блютус больше не нужен, выруби»: expected bluetooth_off, picked bluetooth_on (p 0.62), did none
- laya (convaiinnovations/laya/multilingual) · ru · «блокни комп»: expected lock, picked lock (p 0.64), did none
- laya (convaiinnovations/laya/multilingual) · ru · «щёлкни снимок экрана»: expected screenshot, picked screenshot (p 0.73), did none
- laya (convaiinnovations/laya/multilingual) · ru · «заскринь экран»: expected screenshot, picked brightness_up (p 0.67), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сколько времени уже?»: expected time, picked time (p 0.65), did none
- laya (convaiinnovations/laya/multilingual) · ru · «включи музыку»: expected none, picked wifi_on (p 0.40), did none
- laya (convaiinnovations/laya/multilingual) · ru · «поставь экран на весь размер»: expected none, picked brightness_up (p 0.63), did none
- laya (convaiinnovations/laya/multilingual) · ru · «сколько стоит новая батарея для ноутбука»: expected none, picked battery (p 1.00), did battery
- laya (convaiinnovations/laya/multilingual) · ru · «сколько времени займёт установка»: expected none, picked time (p 0.60), did none
- laya (convaiinnovations/laya/multilingual) · ru · «время обеда, закажи пиццу»: expected none, picked battery (p 0.51), did none
- laya (convaiinnovations/laya/multilingual) · ru · «открой настройки звука»: expected none, picked volume_up (p 0.13), did none
- laya (convaiinnovations/laya/multilingual) · ru · «запиши видео с экрана»: expected none, picked screenshot (p 0.79), did none
- laya (convaiinnovations/laya/multilingual) · ru · «блокнот открой»: expected none, picked battery (p 0.33), did none
- laya (convaiinnovations/laya/multilingual) · ru · «расскажи про яркость звёзд»: expected none, picked brightness_up (p 0.28), did none
- laya (convaiinnovations/laya/multilingual) · ru · «экран моргает, что делать»: expected none, picked battery (p 0.28), did none
- laya (convaiinnovations/laya/multilingual) · ru · «интернет медленный, проверь скорость»: expected none, picked battery (p 0.60), did none
- laya (convaiinnovations/laya/multilingual) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.98), did screenshot
- laya (convaiinnovations/laya/multilingual) · en · «crank it up a bit, I can barely hear»: expected volume_up, picked volume_up (p 0.80), did none
- laya (convaiinnovations/laya/multilingual) · en · «bump the sound up»: expected volume_up, picked brightness_up (p 0.53), did none
- laya (convaiinnovations/laya/multilingual) · en · «too loud, bring it down»: expected volume_down, picked volume_down (p 0.36), did none
- laya (convaiinnovations/laya/multilingual) · en · «turn the sound down, the neighbors complain»: expected volume_down, picked none (p 0.63), did none
- laya (convaiinnovations/laya/multilingual) · en · «kill the sound completely»: expected mute, picked lock (p 0.31), did none
- laya (convaiinnovations/laya/multilingual) · en · «silence the speakers»: expected mute, picked volume_down (p 0.67), did none
- laya (convaiinnovations/laya/multilingual) · en · «bring the sound back»: expected unmute, picked unmute (p 0.29), did none
- laya (convaiinnovations/laya/multilingual) · en · «turn the sound back on»: expected unmute, picked volume_up (p 0.19), did none
- laya (convaiinnovations/laya/multilingual) · en · «the screen is blinding me, dim it»: expected brightness_down, picked lock (p 0.98), did lock
- laya (convaiinnovations/laya/multilingual) · en · «darker screen please»: expected brightness_down, picked brightness_up (p 0.64), did none
- laya (convaiinnovations/laya/multilingual) · en · «why is my wifi so slow?»: expected none, picked wifi_on (p 0.72), did none
- laya (convaiinnovations/laya/multilingual) · en · «play some music»: expected none, picked brightness_up (p 0.19), did none
- laya (convaiinnovations/laya/multilingual) · en · «open the sound settings»: expected none, picked volume_up (p 0.24), did none
- laya (convaiinnovations/laya/multilingual) · en · «record a video of the screen»: expected none, picked screenshot (p 0.54), did none
- laya (convaiinnovations/laya/multilingual) · en · «time to eat, order a pizza»: expected none, picked time (p 0.79), did none
- laya (convaiinnovations/laya/multilingual) · en · «my screen flickers, what should I do»: expected none, picked lock (p 0.81), did none
- laya (Router: checkpoint by language) · ru · «слушай, сделай-ка погромче, ничего не слышно»: expected volume_up, picked volume_up (p 0.21), did none
- laya (Router: checkpoint by language) · ru · «добавь звука»: expected volume_up, picked volume_up (p 0.26), did none
- laya (Router: checkpoint by language) · ru · «звук тихий, прибавь»: expected volume_up, picked volume_down (p 0.50), did none
- laya (Router: checkpoint by language) · ru · «можно чуть громче музыку»: expected volume_up, picked volume_up (p 0.28), did none
- laya (Router: checkpoint by language) · ru · «не слышу ничего, сделай громче»: expected volume_up, picked volume_up (p 0.59), did none
- laya (Router: checkpoint by language) · ru · «слушай, сделай-ка потише, соседи жалуются»: expected volume_down, picked battery (p 0.31), did none
- laya (Router: checkpoint by language) · ru · «убавь звук»: expected volume_down, picked brightness_down (p 0.30), did volume_down
- laya (Router: checkpoint by language) · ru · «слишком громко, приглуши»: expected volume_down, picked volume_up (p 0.58), did none
- laya (Router: checkpoint by language) · ru · «звук поменьше сделай»: expected volume_down, picked battery (p 0.39), did none
- laya (Router: checkpoint by language) · ru · «чуть потише можно»: expected volume_down, picked battery (p 0.34), did none
- laya (Router: checkpoint by language) · ru · «тише давай, уши болят»: expected volume_down, picked volume_down (p 0.44), did none
- laya (Router: checkpoint by language) · ru · «выруби звук совсем»: expected mute, picked mute (p 0.61), did none
- laya (Router: checkpoint by language) · ru · «отключи звук полностью»: expected mute, picked mute (p 0.75), did none
- laya (Router: checkpoint by language) · ru · «сделай тишину, совсем без звука»: expected mute, picked volume_down (p 0.52), did none
- laya (Router: checkpoint by language) · ru · «звук в ноль и выключи»: expected mute, picked battery (p 0.28), did none
- laya (Router: checkpoint by language) · ru · «включи звук обратно»: expected unmute, picked battery (p 0.29), did none
- laya (Router: checkpoint by language) · ru · «звук снова включи пожалуйста»: expected unmute, picked unmute (p 0.40), did none
- laya (Router: checkpoint by language) · ru · «снова хочу слышать звук»: expected unmute, picked volume_up (p 0.24), did none
- laya (Router: checkpoint by language) · ru · «экран тусклый, сделай поярче»: expected brightness_up, picked brightness_up (p 0.58), did none
- laya (Router: checkpoint by language) · ru · «прибавь яркости»: expected brightness_up, picked brightness_up (p 0.90), did none
- laya (Router: checkpoint by language) · ru · «ярче экран пожалуйста»: expected brightness_up, picked brightness_up (p 0.86), did none
- laya (Router: checkpoint by language) · ru · «на экране ничего не видно, яркость выше»: expected brightness_up, picked brightness_up (p 0.35), did none
- laya (Router: checkpoint by language) · ru · «можно экран посветлее»: expected brightness_up, picked battery (p 0.52), did none
- laya (Router: checkpoint by language) · ru · «экран слепит, убавь яркость»: expected brightness_down, picked brightness_up (p 0.54), did none
- laya (Router: checkpoint by language) · ru · «потемнее экран сделай»: expected brightness_down, picked brightness_down (p 0.48), did none
- laya (Router: checkpoint by language) · ru · «яркость поменьше»: expected brightness_down, picked battery (p 0.50), did none
- laya (Router: checkpoint by language) · ru · «глаза режет, притуши экран»: expected brightness_down, picked battery (p 0.60), did none
- laya (Router: checkpoint by language) · ru · «сделай экран темнее на ночь»: expected brightness_down, picked brightness_down (p 0.48), did none
- laya (Router: checkpoint by language) · ru · «врубай вай-фай»: expected wifi_on, picked wifi_on (p 0.31), did none
- laya (Router: checkpoint by language) · ru · «мне нужен вайфай, включи»: expected wifi_on, picked wifi_on (p 0.90), did none
- laya (Router: checkpoint by language) · ru · «вырубай вай фай»: expected wifi_off, picked battery (p 0.70), did none
- laya (Router: checkpoint by language) · ru · «вайфай не нужен, отключай»: expected wifi_off, picked wifi_off (p 0.70), did none
- laya (Router: checkpoint by language) · ru · «отруби беспроводной интернет»: expected wifi_off, picked wifi_on (p 0.46), did none
- laya (Router: checkpoint by language) · ru · «врубай блютус, наушники подключу»: expected bluetooth_on, picked bluetooth_on (p 0.77), did none
- laya (Router: checkpoint by language) · ru · «блютус больше не нужен, выруби»: expected bluetooth_off, picked bluetooth_on (p 0.62), did none
- laya (Router: checkpoint by language) · ru · «блокни комп»: expected lock, picked lock (p 0.64), did none
- laya (Router: checkpoint by language) · ru · «щёлкни снимок экрана»: expected screenshot, picked screenshot (p 0.73), did none
- laya (Router: checkpoint by language) · ru · «заскринь экран»: expected screenshot, picked brightness_up (p 0.67), did none
- laya (Router: checkpoint by language) · ru · «сколько времени уже?»: expected time, picked time (p 0.65), did none
- laya (Router: checkpoint by language) · ru · «включи музыку»: expected none, picked wifi_on (p 0.40), did none
- laya (Router: checkpoint by language) · ru · «поставь экран на весь размер»: expected none, picked brightness_up (p 0.63), did none
- laya (Router: checkpoint by language) · ru · «сколько стоит новая батарея для ноутбука»: expected none, picked battery (p 1.00), did battery
- laya (Router: checkpoint by language) · ru · «сколько времени займёт установка»: expected none, picked time (p 0.60), did none
- laya (Router: checkpoint by language) · ru · «время обеда, закажи пиццу»: expected none, picked battery (p 0.51), did none
- laya (Router: checkpoint by language) · ru · «открой настройки звука»: expected none, picked volume_up (p 0.13), did none
- laya (Router: checkpoint by language) · ru · «запиши видео с экрана»: expected none, picked screenshot (p 0.79), did none
- laya (Router: checkpoint by language) · ru · «блокнот открой»: expected none, picked battery (p 0.33), did none
- laya (Router: checkpoint by language) · ru · «расскажи про яркость звёзд»: expected none, picked brightness_up (p 0.28), did none
- laya (Router: checkpoint by language) · ru · «экран моргает, что делать»: expected none, picked battery (p 0.28), did none
- laya (Router: checkpoint by language) · ru · «интернет медленный, проверь скорость»: expected none, picked battery (p 0.60), did none
- laya (Router: checkpoint by language) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.98), did screenshot
- laya (Router: checkpoint by language) · en · «crank it up a bit, I can barely hear»: expected volume_up, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «louder please»: expected volume_up, picked none (p 0.99), did volume_up
- laya (Router: checkpoint by language) · en · «bump the sound up»: expected volume_up, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «too loud, bring it down»: expected volume_down, picked none (p 0.99), did none
- laya (Router: checkpoint by language) · en · «quieter please»: expected volume_down, picked none (p 1.00), did volume_down
- laya (Router: checkpoint by language) · en · «turn the sound down, the neighbors complain»: expected volume_down, picked none (p 0.97), did none
- laya (Router: checkpoint by language) · en · «kill the sound completely»: expected mute, picked none (p 0.99), did none
- laya (Router: checkpoint by language) · en · «silence the speakers»: expected mute, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «bring the sound back»: expected unmute, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «turn the sound back on»: expected unmute, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «the screen is too dim, brighten it»: expected brightness_up, picked none (p 0.92), did none
- laya (Router: checkpoint by language) · en · «more brightness please»: expected brightness_up, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «the screen is blinding me, dim it»: expected brightness_down, picked none (p 0.87), did none
- laya (Router: checkpoint by language) · en · «darker screen please»: expected brightness_down, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «enable wi-fi please»: expected wifi_on, picked none (p 1.00), did wifi_on
- laya (Router: checkpoint by language) · en · «kill the wifi»: expected wifi_off, picked wifi_on (p 0.62), did none
- laya (Router: checkpoint by language) · en · «disable wi-fi»: expected wifi_off, picked none (p 0.99), did wifi_off
- laya (Router: checkpoint by language) · en · «enable bluetooth, I want my headphones»: expected bluetooth_on, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «switch bluetooth off»: expected bluetooth_off, picked none (p 0.99), did none
- laya (Router: checkpoint by language) · en · «lock the screen, I'm stepping away»: expected lock, picked none (p 0.94), did none
- laya (Router: checkpoint by language) · en · «lock it up»: expected lock, picked none (p 0.98), did none
- laya (Router: checkpoint by language) · en · «grab a screenshot»: expected screenshot, picked none (p 1.00), did none
- laya (Router: checkpoint by language) · en · «capture the screen»: expected screenshot, picked none (p 1.00), did screenshot
- laya (Router: checkpoint by language) · en · «how much charge is left?»: expected battery, picked none (p 0.90), did none
- laya (Router: checkpoint by language) · en · «check the battery»: expected battery, picked none (p 0.99), did none
- laya (Router: checkpoint by language) · en · «what time is it?»: expected time, picked none (p 0.91), did time
- laya (Router: checkpoint by language) · en · «time please»: expected time, picked none (p 1.00), did time
- llm (jackson/decide.py) · ru · «звук тихий, прибавь»: expected volume_up, picked volume_up (p 0.77), did none
- llm (jackson/decide.py) · ru · «снова хочу слышать звук»: expected unmute, picked unmute (p 0.72), did none
- llm (jackson/decide.py) · ru · «на экране ничего не видно, яркость выше»: expected brightness_up, picked brightness_down (p 0.47), did none
- llm (jackson/decide.py) · ru · «глаза режет, притуши экран»: expected brightness_down, picked brightness_down (p 0.90), did none
- llm (jackson/decide.py) · ru · «открой настройки звука»: expected none, picked volume_up (p 0.56), did none
- llm (jackson/decide.py) · ru · «запиши видео с экрана»: expected none, picked screenshot (p 0.95), did screenshot
- llm (jackson/decide.py) · ru · «скинь скриншот в телеграм»: expected none, picked screenshot (p 0.99), did screenshot
- llm (jackson/decide.py) · en · «time to eat, order a pizza»: expected none, picked time (p 0.61), did none
