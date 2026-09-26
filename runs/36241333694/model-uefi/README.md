### VM test: jackson-local-model (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.20 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 10.01 network-online' |
| 8 | terminal | key | ok | 0.0s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.0s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 7.7s | typed 149 characters |
| 13 | install | sleep | ok | 60.0s | slept 60s |
| 14 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   89.061348] sos-vm-test[2209]: SOS-STEP model-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 18 | install | type | ok | 5.3s | typed 103 characters |
| 19 | install | sleep | ok | 6.0s | slept 6s |
| 20 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 21 | install | key | ok | 0.0s | meta_l+q |
| 22 | install | sleep | ok | 2.0s | slept 2s |
| 23 | ask | key | ok | 0.0s | meta_l+j |
| 24 | ask | sleep | ok | 3.0s | slept 3s |
| 25 | ask | type | ok | 1.5s | typed 28 characters |
| 26 | ask | sleep | ok | 8.0s | slept 8s |
| 27 | ask | screenshot | ok | 1.3s | 1440x900 (pillow) |
| 28 | ask | wait_serial | failed | 355.0s | serial reported failure: '[  487.013679] jacksond[1397]: INFO jackson.engine: turn failed after 361135 ms: The model failed: local: no answer from 127.0.0.1:808 |
| 29 | ask | sleep | ok | 2.0s | slept 2s |
| 30 | ask | screenshot | ok | 1.4s | 1440x900 (pillow) |
| 31 | skill | type | ok | 2.5s | typed 48 characters |
| 32 | skill | wait_serial | failed | 365.9s | serial reported failure: '[  857.864569] jacksond[1397]: INFO jackson.engine: turn failed after 360234 ms: The model failed: local: no answer from 127.0.0.1:808 |
| 33 | skill | sleep | ok | 2.0s | slept 2s |
| 34 | skill | screenshot | ok | 1.7s | 1440x900 (pillow) |
| 35 | russian | type | ok | 1.8s | typed 34 characters |
| 36 | russian | wait_serial | failed | 364.1s | serial reported failure: '[ 1228.323053] jacksond[1397]: INFO jackson.engine: turn failed after 360224 ms: The model failed: local: no answer from 127.0.0.1:808 |
| 37 | russian | sleep | ok | 2.0s | slept 2s |
| 38 | russian | screenshot | ok | 1.1s | 1440x900 (pillow) |
| 39 | russian | key | ok | 0.0s | esc |
| 40 | status | key | ok | 0.0s | meta_l+ret |
| 41 | status | sleep | ok | 5.0s | slept 5s |
| 42 | status | type | ok | 2.2s | typed 43 characters |
| 43 | status | sleep | ok | 8.0s | slept 8s |
| 44 | status | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 45 | status | type | ok | 4.3s | typed 83 characters |
| 46 | status | sleep | ok | 3.0s | slept 3s |
