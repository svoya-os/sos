### VM test: live-iso-smoke (bios, kvm) — FAILED

Host: INTEL(R) XEON(R) PLATINUM 8573C

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot-menu | wait_serial | ok | 1.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot-menu | wait_screen | ok | 4.2s | screen has content (75.4% non-background) |
| 3 | boot-menu | screenshot | ok | 0.8s | 1920x1080 (pillow) |
| 4 | boot | key | ok | 0.1s | ret |
| 5 | plymouth | sleep | ok | 10.0s | slept 10s |
| 6 | plymouth | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 7 | desktop | wait_serial | failed | 627.3s | timed out waiting for serial pattern 'SOS-MARK \\S+ desktop-ready' |
