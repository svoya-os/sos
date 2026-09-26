### VM test: games (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 2.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 18.0s | matched 'SOS-MARK 15.93 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 7.95 network-online' |
| 8 | install | key | ok | 0.0s | meta_l+ret |
| 9 | install | sleep | ok | 5.0s | slept 5s |
| 10 | install | key | ok | 0.0s | meta_l+f |
| 11 | install | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 11.7s | typed 229 characters |
| 13 | install | sleep | ok | 90.0s | slept 90s |
| 14 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[  121.235500] sos-vm-test[5519]: SOS-STEP games-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 18 | tools | type | ok | 19.3s | typed 380 characters |
| 19 | tools | wait_serial | failed | 180.3s | timed out waiting for serial pattern 'SOS-STEP tools-shown' |
| 20 | tools | sleep | ok | 2.0s | slept 2s |
| 21 | tools | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 22 | tools | key | ok | 0.0s | meta_l+q |
| 23 | tools | sleep | ok | 2.0s | slept 2s |
| 24 | launcher | key | ok | 0.0s | meta_l+spc |
| 25 | launcher | sleep | ok | 2.0s | slept 2s |
| 26 | launcher | type | ok | 0.3s | typed 5 characters |
| 27 | launcher | sleep | ok | 2.0s | slept 2s |
| 28 | launcher | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 29 | launcher | key | ok | 0.0s | ret |
| 30 | steam | sleep | ok | 20.0s | slept 20s |
| 31 | steam | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 32 | steam | click | ok | 0.1s | clicked 889,568 of 1440x900 |
| 33 | steam | sleep | ok | 60.0s | slept 60s |
| 34 | steam | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 35 | steam | sleep | ok | 180.0s | slept 180s |
| 36 | steam | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 37 | steam | sleep | ok | 240.0s | slept 240s |
| 38 | steam | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 39 | after | key | ok | 0.0s | meta_l+spc |
| 40 | after | sleep | ok | 2.0s | slept 2s |
| 41 | after | type | ok | 0.3s | typed 5 characters |
| 42 | after | sleep | ok | 2.0s | slept 2s |
| 43 | after | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 44 | after | key | ok | 0.0s | esc |
