### VM test: user-journeys (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 2.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 18.0s | matched 'SOS-MARK 16.01 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 7 | cheatsheet | key | ok | 0.0s | meta_l+k |
| 8 | cheatsheet | sleep | ok | 2.0s | slept 2s |
| 9 | cheatsheet | screenshot | ok | 0.8s | 1440x900 (pillow), 34.0% changed vs 01-desktop |
| 10 | cheatsheet | key | ok | 0.0s | esc |
| 11 | cheatsheet | sleep | ok | 1.0s | slept 1s |
| 12 | launcher | key | ok | 0.0s | meta_l+spc |
| 13 | launcher | sleep | ok | 2.0s | slept 2s |
| 14 | launcher | type | ok | 0.2s | typed 4 characters |
| 15 | launcher | sleep | ok | 2.0s | slept 2s |
| 16 | launcher | screenshot | ok | 0.8s | 1440x900 (pillow), 34.2% changed vs 01-desktop |
| 17 | launcher | key | ok | 0.0s | ret |
| 18 | terminal | sleep | ok | 5.0s | slept 5s |
| 19 | terminal | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 20 | doctor-cli | type | ok | 0.6s | typed 11 characters |
| 21 | doctor-cli | sleep | ok | 10.0s | slept 10s |
| 22 | doctor-cli | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 23 | models | type | ok | 1.3s | typed 26 characters |
| 24 | models | sleep | ok | 8.0s | slept 8s |
| 25 | models | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 26 | accent | type | ok | 1.5s | typed 30 characters |
| 27 | accent | sleep | ok | 6.0s | slept 6s |
| 28 | accent | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 29 | accent | type | ok | 1.2s | typed 24 characters |
| 30 | accent | sleep | ok | 6.0s | slept 6s |
| 31 | accent | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 32 | jackson-cli | type | ok | 1.5s | typed 29 characters |
| 33 | jackson-cli | sleep | ok | 15.0s | slept 15s |
| 34 | jackson-cli | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 35 | fun-cli | type | ok | 2.5s | typed 49 characters |
| 36 | fun-cli | sleep | ok | 5.0s | slept 5s |
| 37 | fun-cli | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 38 | apps-cli | type | ok | 1.4s | typed 27 characters |
| 39 | apps-cli | sleep | ok | 6.0s | slept 6s |
| 40 | apps-cli | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 41 | skills-cli | type | ok | 2.8s | typed 56 characters |
| 42 | skills-cli | sleep | ok | 6.0s | slept 6s |
| 43 | skills-cli | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 44 | upsil-cli | type | ok | 4.7s | typed 92 characters |
| 45 | upsil-cli | sleep | ok | 15.0s | slept 15s |
| 46 | upsil-cli | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 47 | upsil-cli | type | ok | 0.3s | typed 5 characters |
| 48 | jackson | key | ok | 0.0s | meta_l+j |
| 49 | jackson | sleep | ok | 3.0s | slept 3s |
| 50 | jackson | type | ok | 1.6s | typed 31 characters |
| 51 | jackson | sleep | ok | 15.0s | slept 15s |
| 52 | jackson | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 53 | jackson-fun | type | ok | 0.6s | typed 12 characters |
| 54 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 55 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 56 | jackson-fun | type | ok | 0.6s | typed 11 characters |
| 57 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 58 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 59 | jackson-fun | type | ok | 0.8s | typed 15 characters |
| 60 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 61 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 62 | jackson-fun | type | ok | 0.5s | typed 10 characters |
| 63 | jackson-fun | sleep | ok | 5.0s | slept 5s |
| 64 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 65 | jackson-fun | type | ok | 0.6s | typed 12 characters |
| 66 | jackson-fun | sleep | ok | 5.0s | slept 5s |
| 67 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 68 | jackson-fun | key | ok | 0.0s | esc |
| 69 | jackson-fun | sleep | ok | 1.0s | slept 1s |
| 70 | jackson-fun | key | ok | 0.0s | meta_l+q |
| 71 | jackson-fun | sleep | ok | 2.0s | slept 2s |
| 72 | jackson-install | key | ok | 0.0s | meta_l+j |
| 73 | jackson-install | sleep | ok | 3.0s | slept 3s |
| 74 | jackson-install | type | ok | 0.9s | typed 17 characters |
| 75 | jackson-install | sleep | ok | 8.0s | slept 8s |
| 76 | jackson-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 77 | jackson-install | type | ok | 0.1s | typed 2 characters |
| 78 | jackson-install | sleep | ok | 2.0s | slept 2s |
| 79 | jackson-install | type | ok | 0.1s | typed 1 characters |
| 80 | jackson-install | sleep | ok | 2.0s | slept 2s |
| 81 | jackson | key | ok | 0.0s | esc |
| 82 | jackson | sleep | ok | 1.0s | slept 1s |
| 83 | launcher-install | key | ok | 0.0s | meta_l+spc |
| 84 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 85 | launcher-install | type | ok | 0.5s | typed 9 characters |
| 86 | launcher-install | sleep | ok | 3.0s | slept 3s |
| 87 | launcher-install | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 88 | launcher-install | key | ok | 0.0s | esc |
| 89 | launcher-install | sleep | ok | 1.0s | slept 1s |
| 90 | launcher-install | key | ok | 0.0s | meta_l+spc |
| 91 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 92 | launcher-install | type | ok | 0.2s | typed 4 characters |
| 93 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 94 | launcher-install | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 95 | launcher-install | key | ok | 0.0s | ret |
| 96 | launcher-install | sleep | ok | 3.0s | slept 3s |
| 97 | launcher-install | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 98 | launcher-install | key | ok | 0.0s | esc |
| 99 | launcher-install | sleep | ok | 1.0s | slept 1s |
| 100 | launcher-eggs | key | ok | 0.0s | meta_l+spc |
| 101 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 102 | launcher-eggs | type | ok | 0.3s | typed 5 characters |
| 103 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 104 | launcher-eggs | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 105 | launcher-eggs | key | ok | 0.0s | ret |
| 106 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 107 | launcher-eggs | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 108 | launcher-eggs | key | ok | 0.0s | meta_l+spc |
| 109 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 110 | launcher-eggs | type | ok | 0.1s | typed 2 characters |
| 111 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 112 | launcher-eggs | key | ok | 0.0s | ret |
| 113 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 114 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 115 | launcher-eggs | key | ok | 0.0s | esc |
| 116 | launcher-eggs | sleep | ok | 1.0s | slept 1s |
| 117 | launcher-eggs | key | ok | 0.0s | meta_l+z |
| 118 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 119 | launcher-eggs | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 120 | launcher-eggs | key | ok | 0.0s | esc |
| 121 | launcher-eggs | sleep | ok | 1.0s | slept 1s |
| 122 | control | key | ok | 0.0s | meta_l+a |
| 123 | control | sleep | ok | 2.0s | slept 2s |
| 124 | control | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 125 | control | key | ok | 0.0s | esc |
| 126 | control | sleep | ok | 1.0s | slept 1s |
| 127 | doctor | key | ok | 0.0s | meta_l+esc |
| 128 | doctor | sleep | ok | 6.0s | slept 6s |
| 129 | doctor | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 130 | doctor | key | ok | 0.0s | esc |
| 131 | doctor | sleep | ok | 1.0s | slept 1s |
| 132 | lock | key | ok | 0.0s | meta_l+l |
| 133 | lock | sleep | ok | 3.0s | slept 3s |
| 134 | lock | type | ok | 0.8s | typed 15 characters |
| 135 | lock | sleep | ok | 2.0s | slept 2s |
| 136 | lock | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 137 | lock | sleep | ok | 5.0s | slept 5s |
| 138 | lock | screenshot | ok | 1.0s | 1440x900 (pillow) |
