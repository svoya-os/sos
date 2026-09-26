### VM test: jackson-local-model (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.26 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | terminal | key | ok | 0.0s | meta_l+ret |
| 8 | terminal | sleep | ok | 5.0s | slept 5s |
| 9 | terminal | key | ok | 0.0s | meta_l+f |
| 10 | terminal | sleep | ok | 2.0s | slept 2s |
| 11 | install | type | ok | 7.7s | typed 149 characters |
| 12 | install | sleep | ok | 60.0s | slept 60s |
| 13 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 14 | install | wait_serial | failed | 0.2s | serial reported failure: '[   61.810410] sos-vm-test[1689]: SOS-STEP model-failed' |
