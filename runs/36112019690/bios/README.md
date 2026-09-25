### VM test: live-iso-smoke (bios, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot-menu | wait_serial | ok | 1.0s | matched 'SOS 26.10' |
| 2 | boot-menu | wait_screen | ok | 4.0s | screen has content (76.1% non-background) |
| 3 | boot-menu | screenshot | ok | 0.2s | 640x480 (pillow) |
| 4 | boot | key | ok | 0.0s | ret |
| 5 | plymouth | sleep | ok | 10.0s | slept 10s |
| 6 | plymouth | screenshot | ok | 0.0s | 1440x900 (pillow) |
| 7 | desktop | wait_serial | ok | 6.0s | matched 'SOS-MARK 14.50 desktop-ready' |
| 8 | desktop | sleep | ok | 8.0s | slept 8s |
| 9 | desktop | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 10 | launcher | key | ok | 0.0s | meta_l+spc |
| 11 | launcher | sleep | ok | 3.0s | slept 3s |
| 12 | launcher | screenshot | ok | 0.1s | 1440x900 (pillow), 1.4% changed vs 03-live-desktop |
| 13 | launcher | key | ok | 0.0s | esc |
| 14 | launcher | sleep | ok | 2.0s | slept 2s |
| 15 | jackson | key | ok | 0.0s | meta_l+j |
| 16 | jackson | sleep | ok | 3.0s | slept 3s |
| 17 | jackson | screenshot | ok | 0.1s | 1440x900 (pillow), 1.4% changed vs 03-live-desktop |
| 18 | jackson | key | ok | 0.0s | esc |
