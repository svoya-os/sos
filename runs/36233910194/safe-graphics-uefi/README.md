### VM test: live-iso-safe-graphics (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot-menu | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot-menu | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot-menu | screenshot | ok | 0.7s | 1280x800 (pillow) |
| 4 | boot | key | ok | 0.0s | down |
| 5 | boot | sleep | ok | 1.0s | slept 1s |
| 6 | boot | screenshot | ok | 0.6s | 1280x800 (pillow) |
| 7 | boot | key | ok | 0.0s | ret |
| 8 | plymouth | sleep | ok | 10.0s | slept 10s |
| 9 | plymouth | screenshot | ok | 0.1s | 1280x800 (pillow) |
| 10 | desktop | wait_serial | failed | 600.6s | timed out waiting for serial pattern 'SOS-MARK \\S+ desktop-ready' |
