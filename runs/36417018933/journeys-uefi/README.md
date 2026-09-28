### VM test: user-journeys (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.17 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | cheatsheet | key | ok | 0.1s | meta_l+k |
| 8 | cheatsheet | sleep | ok | 2.0s | slept 2s |
| 9 | cheatsheet | screenshot | ok | 0.8s | 1440x900 (pillow), 49.4% changed vs 01-desktop |
| 10 | cheatsheet | key | ok | 0.1s | esc |
| 11 | cheatsheet | sleep | ok | 1.0s | slept 1s |
| 12 | launcher | key | ok | 0.1s | meta_l+spc |
| 13 | launcher | sleep | ok | 2.0s | slept 2s |
| 14 | launcher | type | ok | 0.3s | typed 4 characters |
| 15 | launcher | sleep | ok | 2.0s | slept 2s |
| 16 | launcher | screenshot | ok | 0.9s | 1440x900 (pillow), 34.2% changed vs 01-desktop |
| 17 | launcher | key | ok | 0.1s | ret |
| 18 | terminal | sleep | ok | 5.0s | slept 5s |
| 19 | terminal | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 20 | doctor-cli | type | ok | 0.7s | typed 11 characters |
| 21 | doctor-cli | sleep | ok | 10.0s | slept 10s |
| 22 | doctor-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 23 | models | type | ok | 1.6s | typed 26 characters |
| 24 | models | sleep | ok | 8.0s | slept 8s |
| 25 | models | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 26 | model-kits | type | ok | 1.4s | typed 23 characters |
| 27 | model-kits | sleep | ok | 5.0s | slept 5s |
| 28 | model-kits | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 29 | accent | type | ok | 1.9s | typed 30 characters |
| 30 | accent | sleep | ok | 6.0s | slept 6s |
| 31 | accent | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 32 | accent | type | ok | 1.5s | typed 24 characters |
| 33 | accent | sleep | ok | 6.0s | slept 6s |
| 34 | accent | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 35 | jackson-cli | type | ok | 1.8s | typed 29 characters |
| 36 | jackson-cli | sleep | ok | 15.0s | slept 15s |
| 37 | jackson-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 38 | fun-cli | type | ok | 3.1s | typed 49 characters |
| 39 | fun-cli | sleep | ok | 5.0s | slept 5s |
| 40 | fun-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 41 | apps-cli | type | ok | 1.7s | typed 27 characters |
| 42 | apps-cli | sleep | ok | 6.0s | slept 6s |
| 43 | apps-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 44 | skills-cli | type | ok | 3.5s | typed 56 characters |
| 45 | skills-cli | sleep | ok | 6.0s | slept 6s |
| 46 | skills-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 47 | upsil-cli | type | ok | 5.7s | typed 92 characters |
| 48 | upsil-cli | sleep | ok | 15.0s | slept 15s |
| 49 | upsil-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 50 | upsil-cli | type | ok | 0.3s | typed 5 characters |
| 51 | jackson | key | ok | 0.2s | meta_l+j |
| 52 | jackson | sleep | ok | 3.0s | slept 3s |
| 53 | jackson | type | ok | 2.0s | typed 31 characters |
| 54 | jackson | sleep | ok | 15.0s | slept 15s |
| 55 | jackson | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 56 | jackson-fun | type | ok | 0.8s | typed 12 characters |
| 57 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 58 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 59 | jackson-fun | type | ok | 0.7s | typed 11 characters |
| 60 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 61 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 62 | jackson-fun | type | ok | 1.0s | typed 15 characters |
| 63 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 64 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 65 | jackson-fun | type | ok | 0.6s | typed 10 characters |
| 66 | jackson-fun | sleep | ok | 5.0s | slept 5s |
| 67 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 68 | jackson-draw | type | ok | 1.3s | typed 20 characters |
| 69 | jackson-draw | sleep | ok | 5.0s | slept 5s |
| 70 | jackson-draw | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 71 | jackson-fun | type | ok | 0.8s | typed 12 characters |
| 72 | jackson-fun | sleep | ok | 5.0s | slept 5s |
| 73 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 74 | jackson-fun | key | ok | 0.1s | esc |
| 75 | jackson-fun | sleep | ok | 1.0s | slept 1s |
| 76 | jackson-fun | key | ok | 0.1s | meta_l+q |
| 77 | jackson-fun | sleep | ok | 2.0s | slept 2s |
| 78 | jackson-install | key | ok | 0.2s | meta_l+j |
| 79 | jackson-install | sleep | ok | 3.0s | slept 3s |
| 80 | jackson-install | type | ok | 1.1s | typed 17 characters |
| 81 | jackson-install | sleep | ok | 8.0s | slept 8s |
| 82 | jackson-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 83 | jackson-install | type | ok | 0.1s | typed 2 characters |
| 84 | jackson-install | sleep | ok | 2.0s | slept 2s |
| 85 | jackson-install | type | ok | 0.1s | typed 1 characters |
| 86 | jackson-install | sleep | ok | 2.0s | slept 2s |
| 87 | jackson | key | ok | 0.1s | esc |
| 88 | jackson | sleep | ok | 1.0s | slept 1s |
| 89 | launcher-install | key | ok | 0.1s | meta_l+spc |
| 90 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 91 | launcher-install | type | ok | 0.6s | typed 9 characters |
| 92 | launcher-install | sleep | ok | 3.0s | slept 3s |
| 93 | launcher-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 94 | launcher-install | key | ok | 0.1s | esc |
| 95 | launcher-install | sleep | ok | 1.0s | slept 1s |
| 96 | launcher-install | key | ok | 0.1s | meta_l+spc |
| 97 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 98 | launcher-install | type | ok | 0.3s | typed 4 characters |
| 99 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 100 | launcher-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 101 | launcher-install | key | ok | 0.1s | ret |
| 102 | launcher-install | sleep | ok | 3.0s | slept 3s |
| 103 | launcher-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 104 | launcher-install | key | ok | 0.1s | esc |
| 105 | launcher-install | sleep | ok | 1.0s | slept 1s |
| 106 | launcher-eggs | key | ok | 0.1s | meta_l+spc |
| 107 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 108 | launcher-eggs | type | ok | 0.3s | typed 5 characters |
| 109 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 110 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 111 | launcher-eggs | key | ok | 0.1s | ret |
| 112 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 113 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 114 | launcher-eggs | key | ok | 0.1s | meta_l+spc |
| 115 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 116 | launcher-eggs | type | ok | 0.1s | typed 2 characters |
| 117 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 118 | launcher-eggs | key | ok | 0.1s | ret |
| 119 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 120 | launcher-eggs | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 121 | launcher-eggs | key | ok | 0.1s | esc |
| 122 | launcher-eggs | sleep | ok | 1.0s | slept 1s |
| 123 | launcher-eggs | key | ok | 0.1s | meta_l+z |
| 124 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 125 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 126 | launcher-eggs | key | ok | 0.1s | esc |
| 127 | launcher-eggs | sleep | ok | 1.0s | slept 1s |
| 128 | win-tap | key | ok | 0.1s | meta_l |
| 129 | win-tap | sleep | ok | 2.0s | slept 2s |
| 130 | win-tap | type | ok | 0.5s | typed 7 characters |
| 131 | win-tap | sleep | ok | 1.0s | slept 1s |
| 132 | win-tap | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 133 | win-tap | key | ok | 0.1s | esc |
| 134 | win-tap | sleep | ok | 1.0s | slept 1s |
| 135 | overview | key | ok | 0.1s | meta_l+tab |
| 136 | overview | sleep | ok | 3.0s | slept 3s |
| 137 | overview | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 138 | overview | key | ok | 0.1s | esc |
| 139 | overview | sleep | ok | 1.0s | slept 1s |
| 140 | alt-tab | key_down | ok | 0.0s | down alt |
| 141 | alt-tab | key | ok | 0.1s | tab |
| 142 | alt-tab | sleep | ok | 2.0s | slept 2s |
| 143 | alt-tab | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 144 | alt-tab | key_up | ok | 0.0s | up alt |
| 145 | alt-tab | sleep | ok | 2.0s | slept 2s |
| 146 | alt-tab | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 147 | alt-tab | key | ok | 0.1s | alt+tab |
| 148 | alt-tab | sleep | ok | 2.0s | slept 2s |
| 149 | snap | key | ok | 0.1s | meta_l+left |
| 150 | snap | sleep | ok | 2.0s | slept 2s |
| 151 | snap | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 152 | snap | key | ok | 0.1s | meta_l+up |
| 153 | snap | sleep | ok | 2.0s | slept 2s |
| 154 | snap | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 155 | snap | key | ok | 0.1s | meta_l+down |
| 156 | snap | sleep | ok | 2.0s | slept 2s |
| 157 | snap | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 158 | emoji | key | ok | 0.1s | meta_l+dot |
| 159 | emoji | sleep | ok | 2.0s | slept 2s |
| 160 | emoji | type | ok | 0.3s | typed 4 characters |
| 161 | emoji | sleep | ok | 2.0s | slept 2s |
| 162 | emoji | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 163 | emoji | key | ok | 0.1s | esc |
| 164 | emoji | sleep | ok | 1.0s | slept 1s |
| 165 | show-desktop | key | ok | 0.1s | meta_l+d |
| 166 | show-desktop | sleep | ok | 2.0s | slept 2s |
| 167 | show-desktop | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 168 | show-desktop | key | ok | 0.1s | meta_l+d |
| 169 | show-desktop | sleep | ok | 2.0s | slept 2s |
| 170 | show-desktop | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 171 | game-mode | key | ok | 0.1s | meta_l+g |
| 172 | game-mode | sleep | ok | 3.0s | slept 3s |
| 173 | game-mode | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 174 | game-mode | key | ok | 0.1s | meta_l+g |
| 175 | game-mode | sleep | ok | 3.0s | slept 3s |
| 176 | night-light | key | ok | 0.1s | meta_l+ret |
| 177 | night-light | sleep | ok | 4.0s | slept 4s |
| 178 | night-light | type | ok | 4.6s | typed 74 characters |
| 179 | night-light | sleep | ok | 3.0s | slept 3s |
| 180 | night-light | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 181 | night-light | type | ok | 4.2s | typed 68 characters |
| 182 | night-light | sleep | ok | 2.0s | slept 2s |
| 183 | control | key | ok | 0.1s | meta_l+a |
| 184 | control | sleep | ok | 2.0s | slept 2s |
| 185 | control | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 186 | control | key | ok | 0.1s | esc |
| 187 | control | sleep | ok | 1.0s | slept 1s |
| 188 | doctor | key | ok | 0.1s | meta_l+esc |
| 189 | doctor | sleep | ok | 6.0s | slept 6s |
| 190 | doctor | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 191 | doctor | key | ok | 0.1s | esc |
| 192 | doctor | sleep | ok | 1.0s | slept 1s |
| 193 | lock | key | ok | 0.1s | meta_l+l |
| 194 | lock | sleep | ok | 3.0s | slept 3s |
| 195 | lock | type | ok | 1.0s | typed 15 characters |
| 196 | lock | sleep | ok | 2.0s | slept 2s |
| 197 | lock | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 198 | lock | sleep | ok | 5.0s | slept 5s |
| 199 | lock | screenshot | ok | 1.1s | 1440x900 (pillow) |
