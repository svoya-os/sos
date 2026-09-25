import QtQuick
import qs.core
import qs.components

// Step 1 · accessibility (always reachable: Super+Alt+A). Six switches in a
// two-column grid of option rows; every one writes Settings at once and the
// shell (and this wizard) follow live.
Item {
    id: root

    required property var wizard

    Grid {
        width: parent.width
        columns: 2
        columnSpacing: 16
        rowSpacing: 16

        WizOption {
            width: (parent.width - 16) / 2
            title: Strings.wizLargeText
            note: Strings.wzLargeSub
            checked: Settings.largeText
            onToggled: value => Settings.largeText = value
        }
        WizOption {
            width: (parent.width - 16) / 2
            title: Strings.wizHighContrast
            note: Strings.wzContrastSub
            checked: Settings.highContrast
            onToggled: value => Settings.highContrast = value
        }
        WizOption {
            width: (parent.width - 16) / 2
            title: Strings.wizReduceMotion
            note: Strings.wzMotionSub
            checked: Settings.reduceMotion
            onToggled: value => Settings.reduceMotion = value
        }
        WizOption {
            width: (parent.width - 16) / 2
            title: Strings.wizStartupSound
            note: Strings.wzSoundSub
            showPlay: true
            checked: Settings.startupSound
            onToggled: value => Settings.startupSound = value
            onPlayed: Sys.playSound("desktop-login")
        }
        WizOption {
            width: (parent.width - 16) / 2
            title: Strings.wzPostTitle
            note: Strings.wzPostSub
            checked: Settings.post
            onToggled: value => Settings.post = value
        }
        WizOption {
            width: (parent.width - 16) / 2
            title: Strings.wzIdleTitle
            note: Strings.wzIdleSub(Settings.idleLockMinutes)
            checked: Settings.idleLockMinutes > 0
            onToggled: value => Settings.idleLockMinutes = value ? 10 : 0
        }
    }
}
