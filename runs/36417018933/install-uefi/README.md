### VM test: install-to-disk (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 18.0s | matched 'SOS-MARK 15.86 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | installer | key | ok | 0.1s | meta_l+ret |
| 8 | installer | sleep | ok | 8.0s | slept 8s |
| 9 | installer | type | ok | 2.0s | typed 33 characters |
| 10 | installer | wait_serial | failed | 60.7s | timed out waiting for serial pattern 'SOS-STEP installer-start' |
