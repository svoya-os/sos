### VM test: install-to-disk (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.14 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | installer | key | ok | 0.0s | meta_l+ret |
| 8 | installer | sleep | ok | 5.0s | slept 5s |
| 9 | installer | type | ok | 15.8s | typed 309 characters |
| 10 | installer | sleep | ok | 25.0s | slept 25s |
| 11 | welcome | screenshot | ok | 1.0s | 1440x900 (pillow), 31.3% changed vs 01-live-desktop |
| 12 | welcome | key | ok | 0.0s | alt+n |
| 13 | locale | sleep | ok | 4.0s | slept 4s |
| 14 | locale | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 15 | locale | key | ok | 0.0s | alt+n |
| 16 | keyboard | sleep | ok | 4.0s | slept 4s |
| 17 | keyboard | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 18 | keyboard | key | ok | 0.0s | alt+n |
| 19 | partition | sleep | ok | 8.0s | slept 8s |
| 20 | partition | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 21 | partition | key | ok | 0.0s | alt+n |
| 22 | users | sleep | ok | 4.0s | slept 4s |
| 23 | users | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 24 | users | key | ok | 0.0s | tab |
| 25 | users | key | ok | 0.0s | tab |
| 26 | users | key | ok | 0.0s | tab |
| 27 | users | type | ok | 0.8s | typed 16 characters |
| 28 | users | key | ok | 0.0s | tab |
| 29 | users | type | ok | 0.8s | typed 16 characters |
| 30 | users | sleep | ok | 2.0s | slept 2s |
| 31 | users | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 32 | users | key | ok | 0.0s | alt+n |
| 33 | summary | sleep | ok | 5.0s | slept 5s |
| 34 | summary | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 35 | summary | key | ok | 0.0s | alt+i |
| 36 | summary | sleep | ok | 3.0s | slept 3s |
| 37 | summary | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 38 | summary | key | ok | 0.0s | alt+i |
| 39 | install | sleep | ok | 90.0s | slept 90s |
| 40 | install | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 41 | install | wait_serial | failed | 2400.6s | timed out waiting for serial pattern 'sos-installer\\S*: installation finalized' |
