### VM test: jackson-local-model (uefi, kvm) — passed

Host: AMD EPYC 9V45 96-Core Processor

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 2.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 140.0s | matched 'SOS-MARK 138.46 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 95.66 network-online' |
| 8 | terminal | key | ok | 0.1s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.1s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 9.4s | typed 149 characters |
| 13 | install | sleep | ok | 60.0s | slept 60s |
| 14 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[  219.259727] sos-vm-test[2427]: SOS-STEP model-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 18 | install | type | ok | 6.5s | typed 103 characters |
| 19 | install | sleep | ok | 6.0s | slept 6s |
| 20 | install | screenshot | ok | 0.0s | 1440x900 (pillow) |
| 21 | install | key | ok | 0.1s | meta_l+q |
| 22 | install | sleep | ok | 2.0s | slept 2s |
| 23 | ask | key | ok | 0.2s | meta_l+j |
| 24 | ask | sleep | ok | 3.0s | slept 3s |
| 25 | ask | type | ok | 1.8s | typed 28 characters |
| 26 | ask | sleep | ok | 8.0s | slept 8s |
| 27 | ask | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 28 | ask | sleep | ok | 150.0s | slept 150s |
| 29 | ask | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 30 | ask | wait_serial | ok | 82.1s | matched '[  488.965054] jacksond[1579]: INFO jackson.engine: turn done in 241027 ms: local/Qwen3.5-4B-Q4_K_M, 3219+53 tokens' |
| 31 | ask | sleep | ok | 2.0s | slept 2s |
| 32 | ask | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 33 | skill | type | ok | 3.1s | typed 48 characters |
| 34 | skill | wait_serial | ok | 118.1s | matched '[  612.871939] jacksond[1579]: INFO jackson.engine: turn done in 117471 ms: local/Qwen3.5-4B-Q4_K_M, 4486+27 tokens' (#2) |
| 35 | skill | sleep | ok | 2.0s | slept 2s |
| 36 | skill | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 37 | russian | type | ok | 2.2s | typed 34 characters |
| 38 | russian | wait_serial | ok | 26.0s | matched '[  643.069516] jacksond[1579]: INFO jackson.engine: turn done in 24716 ms: local/Qwen3.5-4B-Q4_K_M, 3444+16 tokens' (#3) |
| 39 | russian | sleep | ok | 2.0s | slept 2s |
| 40 | russian | screenshot | ok | 0.7s | 1440x900 (pillow) |
| 41 | russian | key | ok | 0.1s | esc |
| 42 | status | key | ok | 0.1s | meta_l+ret |
| 43 | status | sleep | ok | 5.0s | slept 5s |
| 44 | status | type | ok | 2.7s | typed 43 characters |
| 45 | status | sleep | ok | 8.0s | slept 8s |
| 46 | status | screenshot | ok | 0.0s | 1440x900 (pillow) |
