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
* Power buttons need two presses (3 s window) and use logind (`systemctl suspend|reboot|poweroff`),
  which polkit allows for the active greeter session.
