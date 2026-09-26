### VM test: live-iso-smoke (bios, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot-menu | wait_serial | ok | 1.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot-menu | wait_screen | ok | 4.2s | screen has content (75.4% non-background) |
| 3 | boot-menu | screenshot | ok | 0.9s | 1920x1080 (pillow) |
| 4 | boot | key | ok | 0.0s | ret |
| 5 | plymouth | sleep | ok | 10.0s | slept 10s |
| 6 | plymouth | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 7 | desktop | wait_serial | ok | 10.0s | matched 'SOS-MARK 18.02 desktop-ready' |
| 8 | desktop | sleep | ok | 8.0s | slept 8s |
| 9 | desktop | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 10 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 9.85 network-online' |
| 11 | launcher | key | ok | 0.0s | meta_l+spc |
| 12 | launcher | sleep | ok | 3.0s | slept 3s |
| 13 | launcher | screenshot | ok | 0.7s | 1440x900 (pillow), 28.0% changed vs 03-live-desktop |
| 14 | launcher | key | ok | 0.0s | esc |
| 15 | launcher | sleep | ok | 2.0s | slept 2s |
| 16 | jackson | key | ok | 0.0s | meta_l+j |
| 17 | jackson | sleep | ok | 3.0s | slept 3s |
| 18 | jackson | screenshot | ok | 0.8s | 1440x900 (pillow), 18.6% changed vs 03-live-desktop |
| 19 | jackson | key | ok | 0.0s | esc |
