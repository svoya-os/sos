### VM test: live-iso-smoke (uefi-sb, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot-menu | wait_serial | ok | 2.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot-menu | wait_screen | ok | 4.1s | screen has content (3.3% non-background) |
| 3 | boot-menu | screenshot | ok | 0.1s | 1280x800 (pillow) |
| 4 | boot | key | ok | 0.0s | ret |
| 5 | plymouth | sleep | ok | 10.0s | slept 10s |
| 6 | plymouth | screenshot | ok | 0.0s | 1440x900 (pillow) |
| 7 | desktop | wait_serial | failed | 600.2s | timed out waiting for serial pattern 'SOS-MARK \\S+ desktop-ready' |
