### VM test: games (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 2.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 17.0s | matched 'SOS-MARK 15.71 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 7.61 network-online' |
| 8 | install | key | ok | 0.1s | meta_l+ret |
| 9 | install | sleep | ok | 5.0s | slept 5s |
| 10 | install | key | ok | 0.1s | meta_l+f |
| 11 | install | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 14.6s | typed 229 characters |
| 13 | install | sleep | ok | 90.0s | slept 90s |
| 14 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 15 | install | wait_serial | failed | 2400.1s | timed out waiting for serial pattern 'SOS-STEP games-ready' |
