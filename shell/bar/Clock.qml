import QtQuick
import Quickshell
import qs.core

// «Чт 24 сен» (textDim) + «18:42» (text, 500, 7px apart). Minute precision.
Row {
    id: root

    property var screen: null

    spacing: 7

    SystemClock {
        id: clock

        precision: SystemClock.Minutes
    }

    BarText {
        text: Strings.barDate(clock.date)
    }

    BarText {
        text: Fmt.clock(clock.date)
        color: Theme.text
    }
}
