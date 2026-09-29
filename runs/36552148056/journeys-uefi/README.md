### VM test: user-journeys (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 20.0s | matched 'SOS-MARK 17.73 desktop-ready' |
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
| 20 | doctor-cli | type | ok | 3.5s | typed 56 characters |
| 21 | doctor-cli | wait_serial | ok | 1.0s | matched '[   47.765179] sos-vm-test[1773]: SOS-STEP doctor-typed' |
| 22 | doctor-cli | sleep | ok | 10.0s | slept 10s |
| 23 | doctor-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 24 | models | type | ok | 1.6s | typed 26 characters |
| 25 | models | sleep | ok | 8.0s | slept 8s |
| 26 | models | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 27 | model-kits | type | ok | 1.4s | typed 23 characters |
| 28 | model-kits | sleep | ok | 5.0s | slept 5s |
| 29 | model-kits | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 30 | accent | type | ok | 1.9s | typed 30 characters |
| 31 | accent | sleep | ok | 6.0s | slept 6s |
| 32 | accent | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 33 | accent | type | ok | 1.5s | typed 24 characters |
| 34 | accent | sleep | ok | 6.0s | slept 6s |
| 35 | accent | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 36 | jackson-cli | type | ok | 1.8s | typed 29 characters |
| 37 | jackson-cli | sleep | ok | 15.0s | slept 15s |
| 38 | jackson-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 39 | fun-cli | type | ok | 3.0s | typed 49 characters |
| 40 | fun-cli | sleep | ok | 5.0s | slept 5s |
| 41 | fun-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 42 | apps-cli | type | ok | 1.7s | typed 27 characters |
| 43 | apps-cli | sleep | ok | 6.0s | slept 6s |
| 44 | apps-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 45 | skills-cli | type | ok | 3.5s | typed 56 characters |
| 46 | skills-cli | sleep | ok | 6.0s | slept 6s |
| 47 | skills-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 48 | upsil-cli | type | ok | 5.7s | typed 92 characters |
| 49 | upsil-cli | sleep | ok | 15.0s | slept 15s |
| 50 | upsil-cli | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 51 | upsil-cli | type | ok | 0.3s | typed 5 characters |
| 52 | jackson | key | ok | 0.2s | meta_l+j |
| 53 | jackson | sleep | ok | 3.0s | slept 3s |
| 54 | jackson | type | ok | 2.0s | typed 31 characters |
| 55 | jackson | sleep | ok | 15.0s | slept 15s |
| 56 | jackson | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 57 | jackson-fun | type | ok | 0.8s | typed 12 characters |
| 58 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 59 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 60 | jackson-fun | type | ok | 0.7s | typed 11 characters |
| 61 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 62 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 63 | jackson-fun | type | ok | 1.0s | typed 15 characters |
| 64 | jackson-fun | sleep | ok | 4.0s | slept 4s |
| 65 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 66 | jackson-fun | type | ok | 0.6s | typed 10 characters |
| 67 | jackson-fun | sleep | ok | 5.0s | slept 5s |
| 68 | jackson-fun | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 69 | jackson-draw | type | ok | 1.3s | typed 20 characters |
| 70 | jackson-draw | sleep | ok | 5.0s | slept 5s |
| 71 | jackson-draw | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 72 | jackson-fun | type | ok | 0.8s | typed 12 characters |
| 73 | jackson-fun | sleep | ok | 5.0s | slept 5s |
| 74 | jackson-fun | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 75 | jackson-fun | key | ok | 0.1s | esc |
| 76 | jackson-fun | sleep | ok | 1.0s | slept 1s |
| 77 | jackson-fun | key | ok | 0.1s | meta_l+q |
| 78 | jackson-fun | sleep | ok | 2.0s | slept 2s |
| 79 | jackson-install | key | ok | 0.2s | meta_l+j |
| 80 | jackson-install | sleep | ok | 3.0s | slept 3s |
| 81 | jackson-install | type | ok | 1.1s | typed 17 characters |
| 82 | jackson-install | sleep | ok | 8.0s | slept 8s |
| 83 | jackson-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 84 | jackson-install | type | ok | 0.1s | typed 2 characters |
| 85 | jackson-install | sleep | ok | 2.0s | slept 2s |
| 86 | jackson-install | type | ok | 0.1s | typed 1 characters |
| 87 | jackson-install | sleep | ok | 2.0s | slept 2s |
| 88 | jackson | key | ok | 0.1s | esc |
| 89 | jackson | sleep | ok | 1.0s | slept 1s |
| 90 | launcher-install | key | ok | 0.1s | meta_l+spc |
| 91 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 92 | launcher-install | type | ok | 0.6s | typed 9 characters |
| 93 | launcher-install | sleep | ok | 3.0s | slept 3s |
| 94 | launcher-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 95 | launcher-install | key | ok | 0.1s | esc |
| 96 | launcher-install | sleep | ok | 1.0s | slept 1s |
| 97 | launcher-install | key | ok | 0.1s | meta_l+spc |
| 98 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 99 | launcher-install | type | ok | 0.3s | typed 4 characters |
| 100 | launcher-install | sleep | ok | 2.0s | slept 2s |
| 101 | launcher-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 102 | launcher-install | key | ok | 0.1s | ret |
| 103 | launcher-install | sleep | ok | 3.0s | slept 3s |
| 104 | launcher-install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 105 | launcher-install | key | ok | 0.1s | esc |
| 106 | launcher-install | sleep | ok | 1.0s | slept 1s |
| 107 | launcher-eggs | key | ok | 0.1s | meta_l+spc |
| 108 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 109 | launcher-eggs | type | ok | 0.3s | typed 5 characters |
| 110 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 111 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 112 | launcher-eggs | key | ok | 0.1s | ret |
| 113 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 114 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 115 | launcher-eggs | key | ok | 0.1s | meta_l+spc |
| 116 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 117 | launcher-eggs | type | ok | 0.1s | typed 2 characters |
| 118 | launcher-eggs | sleep | ok | 2.0s | slept 2s |
| 119 | launcher-eggs | key | ok | 0.1s | ret |
| 120 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 121 | launcher-eggs | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 122 | launcher-eggs | key | ok | 0.1s | esc |
| 123 | launcher-eggs | sleep | ok | 1.0s | slept 1s |
| 124 | launcher-eggs | key | ok | 0.1s | meta_l+z |
| 125 | launcher-eggs | sleep | ok | 5.0s | slept 5s |
| 126 | launcher-eggs | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 127 | launcher-eggs | key | ok | 0.1s | esc |
| 128 | launcher-eggs | sleep | ok | 1.0s | slept 1s |
| 129 | win-tap | key | ok | 0.1s | meta_l |
| 130 | win-tap | sleep | ok | 2.0s | slept 2s |
| 131 | win-tap | type | ok | 0.5s | typed 7 characters |
| 132 | win-tap | sleep | ok | 1.0s | slept 1s |
| 133 | win-tap | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 134 | win-tap | key | ok | 0.1s | esc |
| 135 | win-tap | sleep | ok | 1.0s | slept 1s |
| 136 | overview | key | ok | 0.1s | meta_l+tab |
| 137 | overview | sleep | ok | 3.0s | slept 3s |
| 138 | overview | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 139 | overview | key | ok | 0.1s | esc |
| 140 | overview | sleep | ok | 1.0s | slept 1s |
| 141 | alt-tab | key_down | ok | 0.0s | down alt |
| 142 | alt-tab | key | ok | 0.1s | tab |
| 143 | alt-tab | sleep | ok | 2.0s | slept 2s |
| 144 | alt-tab | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 145 | alt-tab | key_up | ok | 0.0s | up alt |
| 146 | alt-tab | sleep | ok | 2.0s | slept 2s |
| 147 | alt-tab | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 148 | alt-tab | key | ok | 0.1s | alt+tab |
| 149 | alt-tab | sleep | ok | 2.0s | slept 2s |
| 150 | snap | key | ok | 0.1s | meta_l+left |
| 151 | snap | sleep | ok | 2.0s | slept 2s |
| 152 | snap | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 153 | snap | key | ok | 0.1s | meta_l+up |
| 154 | snap | sleep | ok | 2.0s | slept 2s |
| 155 | snap | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 156 | snap | key | ok | 0.1s | meta_l+down |
| 157 | snap | sleep | ok | 2.0s | slept 2s |
| 158 | snap | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 159 | emoji | key | ok | 0.1s | meta_l+dot |
| 160 | emoji | sleep | ok | 2.0s | slept 2s |
| 161 | emoji | type | ok | 0.3s | typed 4 characters |
| 162 | emoji | sleep | ok | 2.0s | slept 2s |
| 163 | emoji | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 164 | emoji | key | ok | 0.1s | esc |
| 165 | emoji | sleep | ok | 1.0s | slept 1s |
| 166 | show-desktop | key | ok | 0.1s | meta_l+d |
| 167 | show-desktop | sleep | ok | 2.0s | slept 2s |
| 168 | show-desktop | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 169 | show-desktop | key | ok | 0.1s | meta_l+d |
| 170 | show-desktop | sleep | ok | 2.0s | slept 2s |
| 171 | show-desktop | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 172 | game-mode | key | ok | 0.1s | meta_l+g |
| 173 | game-mode | sleep | ok | 3.0s | slept 3s |
| 174 | game-mode | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 175 | game-mode | key | ok | 0.1s | meta_l+g |
| 176 | game-mode | sleep | ok | 3.0s | slept 3s |
| 177 | night-light | key | ok | 0.1s | meta_l+ret |
| 178 | night-light | sleep | ok | 4.0s | slept 4s |
| 179 | night-light | type | ok | 4.6s | typed 74 characters |
| 180 | night-light | sleep | ok | 3.0s | slept 3s |
| 181 | night-light | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 182 | night-light | type | ok | 4.2s | typed 68 characters |
| 183 | night-light | sleep | ok | 2.0s | slept 2s |
| 184 | control | key | ok | 0.1s | meta_l+a |
| 185 | control | sleep | ok | 2.0s | slept 2s |
| 186 | control | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 187 | control | key | ok | 0.1s | esc |
| 188 | control | sleep | ok | 1.0s | slept 1s |
| 189 | doctor | key | ok | 0.1s | meta_l+esc |
| 190 | doctor | sleep | ok | 6.0s | slept 6s |
| 191 | doctor | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 192 | doctor | key | ok | 0.1s | esc |
| 193 | doctor | sleep | ok | 1.0s | slept 1s |
| 194 | lock | key | ok | 0.1s | meta_l+l |
| 195 | lock | sleep | ok | 3.0s | slept 3s |
| 196 | lock | type | ok | 1.0s | typed 15 characters |
| 197 | lock | sleep | ok | 2.0s | slept 2s |
| 198 | lock | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 199 | lock | sleep | ok | 5.0s | slept 5s |
| 200 | lock | screenshot | ok | 1.1s | 1440x900 (pillow) |
