### VM test: voice (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.35 desktop-ready' |
| 5 | desktop | sleep | ok | 8.0s | slept 8s |
| 6 | desktop | screenshot | ok | 0.6s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 10.12 network-online' |
| 8 | terminal | key | ok | 0.0s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.0s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 6.0s | typed 117 characters |
| 13 | install | sleep | ok | 45.0s | slept 45s |
| 14 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   70.063400] sos-vm-test[2015]: SOS-STEP voice-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 18 | mic | type | ok | 21.4s | typed 416 characters |
| 19 | mic | wait_serial | failed | 300.4s | timed out waiting for serial pattern 'SOS-STEP phrases-ready' |
