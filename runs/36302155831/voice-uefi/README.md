### VM test: voice (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.0s | ret |
| 4 | desktop | wait_serial | ok | 18.0s | matched 'SOS-MARK 15.50 desktop-ready' |
| 5 | desktop | sleep | ok | 8.0s | slept 8s |
| 6 | desktop | screenshot | ok | 0.9s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 7.49 network-online' |
| 8 | terminal | key | ok | 0.0s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.0s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 7.4s | typed 117 characters |
| 13 | install | sleep | ok | 45.0s | slept 45s |
| 14 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   62.837674] sos-vm-test[2084]: SOS-STEP voice-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 18 | mic | type | ok | 6.8s | typed 108 characters |
| 19 | mic | wait_serial | ok | 3.0s | matched '[   96.110486] sos-vm-test[2111]: SOS-STEP mic-ready' |
| 20 | mic | wait_serial | ok | 3.0s | matched '[   98.969400] python[2104]: INFO jackson.voice: voice ready in 2.8 s: parakeet-tdt-0.6b-v3 + gigaam-v3-e2e-rnnt + none' |
| 21 | mic | sleep | ok | 2.0s | slept 2s |
| 22 | mic | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 23 | mic | type | ok | 3.2s | typed 51 characters |
| 24 | talk | wait_serial | ok | 2.0s | matched '[  106.686862] python[2104]: INFO jackson.voice: listening (tap)' |
| 25 | talk | sleep | ok | 1.0s | slept 1s |
| 26 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 27 | talk | wait_serial | ok | 4.0s | matched '[  111.237748] jacksond[1397]: INFO jackson.engine: turn done in 13 ms: jackson/fastpath, 0+0 tokens' |
| 28 | talk | sleep | ok | 1.0s | slept 1s |
| 29 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 30 | talk | wait_serial | ok | 0.0s | matched '[  111.255806] python[2104]: INFO jackson.voice: listening (follow)' |
| 31 | talk | sleep | ok | 1.0s | slept 1s |
| 32 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 33 | talk | wait_serial | ok | 2.0s | matched '[  116.024298] python[2104]: INFO jackson.voice: heard 2.0 s of speech, recognized in 1395 ms (gigaam-v3-e2e-rnnt)' (#2) |
| 34 | talk | sleep | ok | 4.0s | slept 4s |
| 35 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 36 | talk | key | ok | 0.0s | esc |
| 37 | status | type | ok | 4.1s | typed 64 characters |
| 38 | status | sleep | ok | 4.0s | slept 4s |
| 39 | status | screenshot | ok | 0.1s | 1440x900 (pillow) |
