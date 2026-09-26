### VM test: install-to-disk (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.30 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 7 | installer | key | ok | 0.0s | meta_l+ret |
| 8 | installer | sleep | ok | 8.0s | slept 8s |
| 9 | installer | type | ok | 1.7s | typed 33 characters |
| 10 | installer | wait_serial | ok | 2.0s | matched '[   40.994636] sos-vm-test[1786]: SOS-STEP installer-start' |
| 11 | installer | sleep | ok | 25.0s | slept 25s |
| 12 | welcome | screenshot | ok | 0.5s | 1440x900 (pillow), 60.7% changed vs 01-live-desktop |
| 13 | welcome | key | ok | 0.0s | alt+n |
| 14 | locale | sleep | ok | 4.0s | slept 4s |
| 15 | locale | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 16 | locale | key | ok | 0.0s | alt+n |
| 17 | keyboard | sleep | ok | 4.0s | slept 4s |
| 18 | keyboard | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 19 | keyboard | key | ok | 0.0s | alt+n |
| 20 | partition | sleep | ok | 8.0s | slept 8s |
| 21 | partition | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 22 | partition | key | ok | 0.0s | alt+n |
| 23 | users | sleep | ok | 4.0s | slept 4s |
| 24 | users | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 25 | users | key | ok | 0.0s | tab |
| 26 | users | key | ok | 0.0s | tab |
| 27 | users | key | ok | 0.0s | tab |
| 28 | users | type | ok | 0.8s | typed 16 characters |
| 29 | users | key | ok | 0.0s | tab |
| 30 | users | type | ok | 0.8s | typed 16 characters |
| 31 | users | sleep | ok | 2.0s | slept 2s |
| 32 | users | screenshot | ok | 0.5s | 1440x900 (pillow) |
| 33 | users | key | ok | 0.0s | alt+n |
| 34 | summary | sleep | ok | 5.0s | slept 5s |
| 35 | summary | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 36 | summary | key | ok | 0.0s | alt+i |
| 37 | summary | sleep | ok | 3.0s | slept 3s |
| 38 | summary | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 39 | summary | key | ok | 0.0s | alt+i |
| 40 | install | sleep | ok | 90.0s | slept 90s |
| 41 | install | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 42 | install | wait_serial | ok | 86.1s | matched '[  277.759286] sos-installer[9643]: installation finalized' |
| 43 | install | sleep | ok | 30.0s | slept 30s |
| 44 | install | screenshot | ok | 0.4s | 1440x900 (pillow) |
| 45 | reboot | eject | ok | 0.0s | ejected the ISO |
| 46 | reboot | sleep | ok | 2.0s | slept 2s |
| 47 | reboot | reset | ok | 0.0s | reset |
| 48 | reboot | sleep | ok | 20.0s | slept 20s |
| 49 | reboot | screenshot | ok | 0.3s | 1440x900 (pillow) |
| 50 | greeter | sleep | ok | 70.0s | slept 70s |
| 51 | greeter | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 52 | login | type | ok | 0.9s | typed 17 characters |
| 53 | login | sleep | ok | 45.0s | slept 45s |
| 54 | login | screenshot | ok | 0.6s | 1440x900 (pillow), 30.6% changed vs 12-greeter |
| 55 | login | sleep | ok | 30.0s | slept 30s |
| 56 | login | screenshot | ok | 0.6s | 1440x900 (pillow) |
