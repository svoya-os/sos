### VM test: games (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 20.0s | matched 'SOS-MARK 18.03 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.1s | 1440x900 (pillow) |
| 7 | install | key | ok | 0.0s | meta_l+ret |
| 8 | install | sleep | ok | 5.0s | slept 5s |
| 9 | install | key | ok | 0.0s | meta_l+f |
| 10 | install | sleep | ok | 2.0s | slept 2s |
| 11 | install | type | ok | 11.8s | typed 229 characters |
| 12 | install | sleep | ok | 90.0s | slept 90s |
| 13 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 14 | install | wait_serial | failed | 0.2s | serial reported failure: '[   69.576937] sos-vm-test[1704]: SOS-STEP games-failed' |
