### VM test: live-iso-smoke (uefi-sb, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot-menu | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot-menu | wait_screen | ok | 4.1s | screen has content (3.3% non-background) |
| 3 | boot-menu | screenshot | ok | 0.2s | 1280x800 (pillow) |
| 4 | boot | key | ok | 0.0s | ret |
| 5 | plymouth | sleep | ok | 10.0s | slept 10s |
| 6 | plymouth | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 7 | desktop | wait_serial | ok | 11.0s | matched 'SOS-MARK 17.80 desktop-ready' |
| 8 | desktop | sleep | ok | 8.0s | slept 8s |
| 9 | desktop | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 10 | launcher | key | ok | 0.0s | meta_l+spc |
| 11 | launcher | sleep | ok | 3.0s | slept 3s |
| 12 | launcher | screenshot | ok | 0.9s | 1440x900 (pillow), 31.6% changed vs 03-live-desktop |
| 13 | launcher | key | ok | 0.0s | esc |
| 14 | launcher | sleep | ok | 2.0s | slept 2s |
| 15 | jackson | key | ok | 0.0s | meta_l+j |
| 16 | jackson | sleep | ok | 3.0s | slept 3s |
| 17 | jackson | screenshot | ok | 1.1s | 1440x900 (pillow), 21.8% changed vs 03-live-desktop |
| 18 | jackson | key | ok | 0.0s | esc |
