### VM test: jackson-local-model (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 21.0s | matched 'SOS-MARK 18.01 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 9.85 network-online' |
| 8 | terminal | key | ok | 0.0s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.0s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 7.7s | typed 149 characters |
| 13 | install | sleep | ok | 60.0s | slept 60s |
| 14 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   93.681270] sos-vm-test[2232]: SOS-STEP model-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 18 | install | type | ok | 5.3s | typed 103 characters |
| 19 | install | sleep | ok | 6.0s | slept 6s |
| 20 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 21 | install | type | ok | 6.6s | typed 127 characters |
| 22 | install | sleep | ok | 6.0s | slept 6s |
| 23 | install | key | ok | 0.0s | meta_l+q |
| 24 | install | sleep | ok | 2.0s | slept 2s |
| 25 | ask | key | ok | 0.0s | meta_l+j |
| 26 | ask | sleep | ok | 3.0s | slept 3s |
| 27 | ask | type | ok | 1.5s | typed 28 characters |
| 28 | ask | sleep | ok | 8.0s | slept 8s |
| 29 | ask | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 30 | ask | wait_serial | ok | 450.6s | matched '[  595.402047] jacksond[2254]: INFO jackson.engine: turn done in 456911 ms: local/Qwen3.5-4B-Q4_K_M, 2949+47 tokens' |
| 31 | ask | sleep | ok | 2.0s | slept 2s |
| 32 | ask | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 33 | skill | type | ok | 2.5s | typed 48 characters |
| 34 | skill | wait_serial | ok | 175.2s | matched '[  776.062351] jacksond[2254]: INFO jackson.engine: turn done in 171472 ms: local/Qwen3.5-4B-Q4_K_M, 3803+35 tokens' (#2) |
| 35 | skill | sleep | ok | 2.0s | slept 2s |
| 36 | skill | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 37 | russian | type | ok | 1.8s | typed 34 characters |
| 38 | russian | wait_serial | ok | 106.2s | matched '[  887.123392] jacksond[2254]: INFO jackson.engine: turn done in 103680 ms: local/Qwen3.5-4B-Q4_K_M, 6428+52 tokens' (#3) |
| 39 | russian | sleep | ok | 2.0s | slept 2s |
| 40 | russian | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 41 | russian | key | ok | 0.0s | esc |
| 42 | status | key | ok | 0.0s | meta_l+ret |
| 43 | status | sleep | ok | 5.0s | slept 5s |
| 44 | status | type | ok | 2.2s | typed 43 characters |
| 45 | status | sleep | ok | 8.0s | slept 8s |
| 46 | status | screenshot | ok | 0.1s | 1440x900 (pillow) |
