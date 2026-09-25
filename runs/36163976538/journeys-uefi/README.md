### VM test: user-journeys (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 2.0s | matched 'SOS 26.10' |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (3.3% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 16.0s | matched 'SOS-MARK 14.46 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 7 | cheatsheet | key | ok | 0.0s | meta_l+k |
| 8 | cheatsheet | sleep | ok | 2.0s | slept 2s |
| 9 | cheatsheet | screenshot | ok | 0.4s | 1440x900 (pillow), 30.4% changed vs 01-desktop |
| 10 | cheatsheet | key | ok | 0.0s | esc |
| 11 | cheatsheet | sleep | ok | 1.0s | slept 1s |
| 12 | launcher | key | ok | 0.0s | meta_l+spc |
| 13 | launcher | sleep | ok | 2.0s | slept 2s |
| 14 | launcher | type | ok | 0.2s | typed 4 characters |
| 15 | launcher | sleep | ok | 2.0s | slept 2s |
| 16 | launcher | screenshot | ok | 0.4s | 1440x900 (pillow), 26.5% changed vs 01-desktop |
| 17 | launcher | key | ok | 0.0s | ret |
| 18 | terminal | sleep | ok | 5.0s | slept 5s |
| 19 | terminal | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 20 | doctor-cli | type | ok | 0.6s | typed 11 characters |
| 21 | doctor-cli | sleep | ok | 10.0s | slept 10s |
| 22 | doctor-cli | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 23 | models | type | ok | 1.3s | typed 26 characters |
| 24 | models | sleep | ok | 8.0s | slept 8s |
| 25 | models | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 26 | accent | type | ok | 1.5s | typed 30 characters |
| 27 | accent | sleep | ok | 6.0s | slept 6s |
| 28 | accent | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 29 | accent | type | ok | 1.2s | typed 24 characters |
| 30 | accent | sleep | ok | 6.0s | slept 6s |
| 31 | accent | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 32 | jackson-cli | type | ok | 1.5s | typed 29 characters |
| 33 | jackson-cli | sleep | ok | 15.0s | slept 15s |
| 34 | jackson-cli | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 35 | jackson | key | ok | 0.0s | meta_l+j |
| 36 | jackson | sleep | ok | 3.0s | slept 3s |
| 37 | jackson | type | ok | 1.6s | typed 31 characters |
| 38 | jackson | sleep | ok | 15.0s | slept 15s |
| 39 | jackson | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 40 | jackson | key | ok | 0.0s | esc |
| 41 | jackson | sleep | ok | 1.0s | slept 1s |
| 42 | control | key | ok | 0.0s | meta_l+a |
| 43 | control | sleep | ok | 2.0s | slept 2s |
| 44 | control | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 45 | control | key | ok | 0.0s | esc |
| 46 | control | sleep | ok | 1.0s | slept 1s |
| 47 | doctor | key | ok | 0.0s | meta_l+esc |
| 48 | doctor | sleep | ok | 6.0s | slept 6s |
| 49 | doctor | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 50 | doctor | key | ok | 0.0s | esc |
| 51 | doctor | sleep | ok | 1.0s | slept 1s |
| 52 | lock | key | ok | 0.0s | meta_l+l |
| 53 | lock | sleep | ok | 3.0s | slept 3s |
| 54 | lock | type | ok | 0.8s | typed 15 characters |
| 55 | lock | sleep | ok | 2.0s | slept 2s |
| 56 | lock | screenshot | ok | 0.4s | 1440x900 (pillow) |
