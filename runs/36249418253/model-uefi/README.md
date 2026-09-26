### VM test: jackson-local-model (uefi, kvm) — FAILED

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 20.0s | matched 'SOS-MARK 17.80 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 9.65 network-online' |
| 8 | terminal | key | ok | 0.0s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.0s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 7.7s | typed 149 characters |
| 13 | install | sleep | ok | 60.0s | slept 60s |
| 14 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   87.095569] sos-vm-test[2228]: SOS-STEP model-ready' |
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
| 28 | ask | wait_serial | failed | 295.7s | serial reported failure: '[  426.371187] jacksond[1393]: INFO jackson.engine: turn failed after 301033 ms: The local model never answered — it may still be load |
| 29 | ask | sleep | ok | 2.0s | slept 2s |
| 30 | ask | screenshot | ok | 1.4s | 1440x900 (pillow) |
| 31 | skill | type | ok | 2.5s | typed 48 characters |
| 32 | skill | wait_serial | failed | 305.6s | serial reported failure: '[  737.906362] jacksond[1393]: INFO jackson.engine: turn failed after 300117 ms: The local model never answered — it may still be load |
| 33 | skill | sleep | ok | 2.0s | slept 2s |
| 34 | skill | screenshot | ok | 1.5s | 1440x900 (pillow) |
| 35 | russian | type | ok | 1.8s | typed 34 characters |
| 36 | russian | wait_serial | failed | 303.4s | serial reported failure: '[ 1047.834054] jacksond[1393]: INFO jackson.engine: turn failed after 300113 ms: The local model never answered — it may still be load |
| 37 | russian | sleep | ok | 2.0s | slept 2s |
| 38 | russian | screenshot | ok | 1.2s | 1440x900 (pillow) |
| 39 | russian | key | ok | 0.0s | esc |
| 40 | status | key | ok | 0.0s | meta_l+ret |
| 41 | status | sleep | ok | 5.0s | slept 5s |
| 42 | status | type | ok | 2.2s | typed 43 characters |
| 43 | status | sleep | ok | 8.0s | slept 8s |
| 44 | status | screenshot | ok | 0.2s | 1440x900 (pillow) |
