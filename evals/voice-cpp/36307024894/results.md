## Jackson's characters on a processor (qwen3-tts.cpp, Qwen3-TTS 0.6B Base)

RTF: seconds of work per second of speech on this runner (model loading not counted; under 1 keeps up with speech). PyTorch on the same kind of runner: about 6 for 0.6B (Voice samples run 36266187438). CER: share of characters Jackson's recognizers hear differently from the line.

| variant | character | RTF | CER | lines |
|---|---|---|---|---|
| q8_0 | Кентафурик | 4.10 | 0.144 | 6/6 |
| q8_0 | Спокойный (в духе Джарвиса) | 4.05 | 0.145 | 6/6 |
| q8_0 | Диспетчер | 3.99 | 0.151 | 6/6 |
| q8_0 | Пиратское радио | 4.22 | 0.151 | 6/6 |
| f16 | Кентафурик | 4.31 | 0.145 | 6/6 |

### What the recognizers heard

- `q8_0/kent/ru-hello` (3.26 s, RTF 4.65, CER 0.029): Здорова! Я Джексон. Говори, что делаем?
- `q8_0/kent/ru-done` (6.78 s, RTF 3.87, CER 0.512): Готово. Громкость 70%. Среча в 15:30, 15:30. До неё 2 часа.
- `q8_0/kent/ru-check` (6.14 s, RTF 3.96, CER 0.0): Проверил систему, всё чисто. Процессор отдыхает, памяти свободно две трети. Можем работать.
- `q8_0/kent/en-hello` (2.46 s, RTF 5.17, CER 0.0): Hey, I'm Jackson what are we doing?
- `q8_0/kent/en-done` (6.22 s, RTF 3.92, CER 0.325): Done? Volume at 70%? The meeting is at 3 30 p.m. two hours from now.
- `q8_0/kent/en-check` (6.86 s, RTF 3.99, CER 0.0): System check complete. All clear. The processor is resting and two thirds of the memory are free. Let's get to work.
- `q8_0/calm/ru-hello` (3.9 s, RTF 4.49, CER 0.057): Здорово. Я Джексон. Говори, что делаем?
- `q8_0/calm/ru-done` (6.94 s, RTF 3.91, CER 0.488): Готово. Громкость 70%. Встреча в 15:30. До неё 2 часа.
- `q8_0/calm/ru-check` (7.82 s, RTF 3.83, CER 0.0): Проверил систему, всё чисто. Процессор отдыхает, памяти свободно две трети. Можем работать.
- `q8_0/calm/en-hello` (2.14 s, RTF 5.61, CER 0.0): Hey, I'm Jackson, what are we doing?
- `q8_0/calm/en-done` (6.06 s, RTF 3.99, CER 0.325): Done, volume at 70%, the meeting is at 3.30 p.m. two hours from now.
- `q8_0/calm/en-check` (7.9 s, RTF 3.78, CER 0.0): System check complete. All clear. The processor is resting and two thirds of the memory are free. Let's get to work.
- `q8_0/dispatcher/ru-hello` (3.1 s, RTF 4.79, CER 0.057): Здорово! Я Джексон. Говори, что делаем.
- `q8_0/dispatcher/ru-done` (7.02 s, RTF 3.85, CER 0.524): Готово. Громкость 70%. Встреча в 15:30 и 15:30. До неё 2 ч.
- `q8_0/dispatcher/ru-check` (6.06 s, RTF 3.98, CER 0.0): Проверил систему, всё чисто. Процессор отдыхает, памяти свободно, две трети. Можем работать.
- `q8_0/dispatcher/en-hello` (2.06 s, RTF 4.79, CER 0.0): Hey, I'm Jackson. What are we doing?
- `q8_0/dispatcher/en-done` (5.1 s, RTF 3.79, CER 0.325): Done. Volume at 70%. The meeting is at 3.30 p.m. Two hours from now.
- `q8_0/dispatcher/en-check` (6.46 s, RTF 3.66, CER 0.0): System check complete. All clear. The processor is resting and two thirds of the memory are free. Let's get to work
- `q8_0/pirate/ru-hello` (4.22 s, RTF 4.86, CER 0.057): Здорово! Я Джексон. Говори, что делаем.
- `q8_0/pirate/ru-done` (7.74 s, RTF 4.07, CER 0.537): Готово! Громкость 70%, встреча в 15:30 до неё 2:00.
- `q8_0/pirate/ru-check` (8.38 s, RTF 4.03, CER 0.0): Проверил систему, всё чисто. Процессор отдыхает, памяти свободно две трети. Можем работать.
- `q8_0/pirate/en-hello` (3.42 s, RTF 5.01, CER 0.0): Hey, I'm Jackson what are we doing?
- `q8_0/pirate/en-done` (7.1 s, RTF 4.05, CER 0.313): Done? Volume at 70%. The meeting is at 3.30 pm, two hours from now.
- `q8_0/pirate/en-check` (7.34 s, RTF 4.01, CER 0.0): System check complete. All clear. The processor is resting and two thirds of the memory are free. Let's get to work.
- `f16/kent/ru-hello` (3.26 s, RTF 4.85, CER 0.057): Здорово! Я Джексон. Говори, что делаем.
- `f16/kent/ru-done` (5.98 s, RTF 4.17, CER 0.488): Готово. Громкость 70%. Встреча в 15:30, до неё 2 часа.
- `f16/kent/ru-check` (6.7 s, RTF 4.10, CER 0.0): Проверил систему, всё чисто. Процессор отдыхает, памяти свободно две трети. Можем работать.
- `f16/kent/en-hello` (2.3 s, RTF 5.51, CER 0.0): Hey, I'm Jackson. What are we doing?
- `f16/kent/en-done` (5.5 s, RTF 4.27, CER 0.325): Done. Volume at 70%. The meeting is at 3.30 p.m., two hours from now.
- `f16/kent/en-check` (7.18 s, RTF 4.05, CER 0.0): System check complete. All clear, the processor is resting and two thirds of the memory are free. Let's get to work.
