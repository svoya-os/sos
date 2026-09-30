### VM test: jackson-local-model (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 16.0s | matched 'SOS-MARK 14.17 desktop-ready' |
| 5 | desktop | sleep | ok | 10.0s | slept 10s |
| 6 | desktop | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 7.15 network-online' |
| 8 | terminal | key | ok | 0.1s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.1s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 9.3s | typed 149 characters |
| 13 | install | sleep | ok | 60.0s | slept 60s |
| 14 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   67.227691] sos-vm-test[2212]: SOS-STEP model-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 18 | install | type | ok | 6.5s | typed 103 characters |
| 19 | install | sleep | ok | 6.0s | slept 6s |
| 20 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 21 | install | key | ok | 0.1s | meta_l+q |
| 22 | install | sleep | ok | 2.0s | slept 2s |
| 23 | ask | key | ok | 0.2s | meta_l+j |
| 24 | ask | sleep | ok | 3.0s | slept 3s |
| 25 | ask | type | ok | 1.8s | typed 28 characters |
| 26 | ask | sleep | ok | 8.0s | slept 8s |
| 27 | ask | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 28 | ask | sleep | ok | 150.0s | slept 150s |
| 29 | ask | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 30 | ask | wait_serial | ok | 44.0s | matched '[  326.865676] jacksond[1393]: INFO jackson.engine: turn done in 203152 ms: local/Qwen3.5-4B-Q4_K_M, 3118+64 tokens' |
| 31 | ask | sleep | ok | 2.0s | slept 2s |
| 32 | ask | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 33 | skill | type | ok | 3.0s | typed 48 characters |
| 34 | skill | wait_serial | ok | 84.1s | matched '[  416.887447] jacksond[1393]: INFO jackson.engine: turn done in 83491 ms: local/Qwen3.5-4B-Q4_K_M, 4110+34 tokens' (#2) |
| 35 | skill | sleep | ok | 2.0s | slept 2s |
| 36 | skill | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 37 | russian | type | ok | 2.1s | typed 34 characters |
| 38 | russian | wait_serial | ok | 31.0s | matched '[  452.695051] jacksond[1393]: INFO jackson.engine: turn done in 30306 ms: local/Qwen3.5-4B-Q4_K_M, 3361+16 tokens' (#3) |
| 39 | russian | sleep | ok | 2.0s | slept 2s |
| 40 | russian | screenshot | ok | 0.8s | 1440x900 (pillow) |
| 41 | russian | key | ok | 0.1s | esc |
| 42 | status | key | ok | 0.1s | meta_l+ret |
| 43 | status | sleep | ok | 5.0s | slept 5s |
| 44 | status | type | ok | 2.6s | typed 43 characters |
| 45 | status | sleep | ok | 8.0s | slept 8s |
| 46 | status | screenshot | ok | 0.0s | 1440x900 (pillow) |
