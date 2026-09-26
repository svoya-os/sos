### VM test: games (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 2.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 16.0s | matched 'SOS-MARK 14.42 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 7.42 network-online' |
| 8 | install | key | ok | 0.0s | meta_l+ret |
| 9 | install | sleep | ok | 5.0s | slept 5s |
| 10 | install | key | ok | 0.0s | meta_l+f |
| 11 | install | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 11.6s | typed 229 characters |
| 13 | install | sleep | ok | 90.0s | slept 90s |
| 14 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[  117.866216] sos-vm-test[5487]: SOS-STEP games-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 18 | tools | type | ok | 9.7s | typed 191 characters |
| 19 | tools | sleep | ok | 8.0s | slept 8s |
| 20 | tools | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 21 | tools | key | ok | 0.0s | meta_l+q |
| 22 | tools | sleep | ok | 2.0s | slept 2s |
| 23 | launcher | key | ok | 0.0s | meta_l+spc |
| 24 | launcher | sleep | ok | 2.0s | slept 2s |
| 25 | launcher | type | ok | 0.3s | typed 5 characters |
| 26 | launcher | sleep | ok | 2.0s | slept 2s |
| 27 | launcher | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 28 | launcher | key | ok | 0.0s | ret |
| 29 | steam | sleep | ok | 45.0s | slept 45s |
| 30 | steam | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 31 | steam | sleep | ok | 120.0s | slept 120s |
| 32 | steam | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 33 | steam | sleep | ok | 180.0s | slept 180s |
| 34 | steam | screenshot | ok | 0.5s | 1440x900 (pillow) |
