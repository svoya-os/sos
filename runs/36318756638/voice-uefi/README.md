### VM test: voice (uefi, kvm) — passed

| # | step | action | status | time | detail |
|---|---|---|---|---|---|
| 1 | boot | wait_serial | ok | 3.0s | matched "before booting or `c' for a command-line.                           \x1b[5;80H \x1b[7m\x1b[5;3H*SOS 26.10  ?  ???                                       |
| 2 | boot | wait_screen | ok | 4.1s | screen has content (76.7% non-background) |
| 3 | boot | key | ok | 0.1s | ret |
| 4 | desktop | wait_serial | ok | 18.0s | matched 'SOS-MARK 16.23 desktop-ready' |
| 5 | desktop | sleep | ok | 8.0s | slept 8s |
| 6 | desktop | screenshot | ok | 1.0s | 1440x900 (pillow) |
| 7 | network | wait_serial | ok | 0.0s | matched 'SOS-MARK 8.23 network-online' |
| 8 | terminal | key | ok | 0.1s | meta_l+ret |
| 9 | terminal | sleep | ok | 5.0s | slept 5s |
| 10 | terminal | key | ok | 0.1s | meta_l+f |
| 11 | terminal | sleep | ok | 2.0s | slept 2s |
| 12 | install | type | ok | 7.4s | typed 117 characters |
| 13 | install | sleep | ok | 45.0s | slept 45s |
| 14 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 15 | install | wait_serial | ok | 0.0s | matched '[   67.707966] sos-vm-test[2123]: SOS-STEP voice-ready' |
| 16 | install | sleep | ok | 2.0s | slept 2s |
| 17 | install | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 18 | mic | type | ok | 6.8s | typed 108 characters |
| 19 | mic | wait_serial | ok | 3.0s | matched '[   96.177873] sos-vm-test[2150]: SOS-STEP mic-ready' |
| 20 | mic | wait_serial | ok | 4.0s | matched '[  100.186194] python[2143]: INFO jackson.voice: voice ready in 3.9 s: parakeet-tdt-0.6b-v3 + gigaam-v3-e2e-rnnt + supertonic-3' |
| 21 | mic | sleep | ok | 2.0s | slept 2s |
| 22 | mic | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 23 | mic | type | ok | 3.2s | typed 51 characters |
| 24 | talk | wait_serial | ok | 2.0s | matched '[  107.739620] python[2143]: INFO jackson.voice: listening (tap)' |
| 25 | talk | sleep | ok | 1.0s | slept 1s |
| 26 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 27 | talk | wait_serial | ok | 4.0s | matched '[  113.223374] jacksond[1398]: INFO jackson.engine: turn done in 10 ms: jackson/fastpath, 0+0 tokens' |
| 28 | talk | sleep | ok | 1.0s | slept 1s |
| 29 | talk | screenshot | ok | 0.2s | 1440x900 (pillow) |
| 30 | talk | wait_serial | ok | 9.0s | matched '[  123.258232] python[2143]: INFO jackson.voice: listening (follow)' |
| 31 | talk | sleep | ok | 1.0s | slept 1s |
| 32 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 33 | talk | wait_serial | ok | 5.0s | matched '[  128.549053] python[2143]: INFO jackson.voice: heard 2.0 s of speech, recognized in 1711 ms (gigaam-v3-e2e-rnnt; sure: parakeet-tdt-0.6b-v3 0.99, gig |
| 34 | talk | sleep | ok | 4.0s | slept 4s |
| 35 | talk | screenshot | ok | 0.1s | 1440x900 (pillow) |
| 36 | talk | key | ok | 0.1s | esc |
| 37 | status | type | ok | 4.0s | typed 64 characters |
| 38 | status | sleep | ok | 4.0s | slept 4s |
| 39 | status | screenshot | ok | 0.1s | 1440x900 (pillow) |
