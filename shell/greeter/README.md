# SOS greeter

The login screen: a Quickshell config (`shell.qml`) that talks to greetd, shown by a small Hyprland
(`hyprland.conf`, entered through `/usr/share/svoya/hypr/greeter.conf`). It shares `core/`,
`components/` and `assets/` with the shell through symlinks, so it matches the lock screen.

```
greetd (/etc/svoya/greetd.toml, user svoya-greeter)
  └─ /usr/lib/svoya/greeter-session
       └─ Hyprland --config /usr/share/svoya/hypr/greeter.conf
            └─ quickshell -p /usr/share/svoya/shell/greeter
                 └─ Greetd.launch(<session Exec>)  →  /usr/bin/svoya-session
```

## Try it without logging out

Inside a running session (no greetd socket, so logging in is refused politely):

    quickshell -p /usr/share/svoya/shell/greeter

Against a real greetd, from a spare VT:

    sudo greetd --config /etc/svoya/greetd.toml    # or restart greetd.service

## Fallback: tuigreet / agreety

If the graphical greeter cannot start (Quickshell missing, GPU trouble), `greeter-session` already
falls back to greetd's text greeter `agreety`. For a nicer text login, install `tuigreet` and point
`/etc/svoya/greetd.toml` at it:

```toml
[terminal]
vt = 7

[default_session]
command = "tuigreet --time --remember --remember-session --asterisks --sessions /usr/share/wayland-sessions --cmd /usr/bin/svoya-session"
user = "svoya-greeter"
```

then `sudo systemctl restart greetd`. Undo by restoring the `command = "/usr/lib/svoya/greeter-session"`
line. tuigreet remembers the last user in `/var/cache/tuigreet`, which must be writable by
`svoya-greeter`.

## Notes

* Users: `/etc/passwd`, uid 1000–59999 with a login shell; avatars from
  `/var/lib/AccountsService/icons/<user>` (the user's `~/.face` is usually not readable here).
* Sessions: `/usr/share/wayland-sessions/*.desktop`, SOS first.
* The greeter remembers the last user, session and login times in its own state directory
  (`/var/lib/svoya-greeter/.local/state/quickshell/…/greeter.json`).
* RU/EN switches the greeter's language only; the session keeps the user's locale.
* Restart and shut down need two presses (3 s window); all power actions use logind
  (`systemctl suspend|reboot|poweroff`), which polkit allows for the active greeter session.
* Look: «Линия» + Jackson (DESIGN §12, `design/mockups/greeter.html`): the boot line through the middle,
  the password typed onto it as dots, Jackson standing on it. `/etc/svoya/theme.json` (written by
  `sos theme apply --system`, always a dark base; the first user's choice by default: «Использовать на
  экране входа» in the wizard and the control center). Missing → Graphite + «Сигнал». The accent colors
  only the caret. Jackson's look: `/etc/svoya/avatar.json`, exported by the same `--system` step
  (`cli/svoya_cli/theme/avatar_export.py`, validated on the root side); missing → the default Jackson.
* After PAM says yes the greeter waits 460 ms (the grin and the sweep) before starting the session;
  with reduce motion it starts at once.
