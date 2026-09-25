import QtQuick
import Quickshell
import qs.core

// Lock screen / greeter clock (design/mockups/components.css .clock/.date):
// Plex Sans Light 96/100 with tabular figures, the colon in textDim lifted by
// 6px; below it (10px gap) the date in mono 12/16, +0.14em, uppercase.
// Height 126: the 100px clock line box, 10px gap, the 16px date line box.
Item {
    id: root

    implicitWidth: Math.max(clockRow.implicitWidth, date.implicitWidth)
    implicitHeight: 126

    SystemClock {
        id: clock

        precision: SystemClock.Minutes
    }

    component Digits: Text {
        height: 100
        verticalAlignment: Text.AlignVCenter
        color: Theme.text
        font.family: Theme.sans
        font.pixelSize: Theme.fsDisplay
        font.weight: Font.Light
        font.features: Theme.tabularFeatures
        font.letterSpacing: -0.005 * Theme.fsDisplay
        textFormat: Text.PlainText
    }

    Row {
        id: clockRow

        anchors.horizontalCenter: parent.horizontalCenter

        Digits {
            text: Qt.formatTime(clock.date, "hh")
        }
        Digits {
            y: -6
            leftPadding: 2
            rightPadding: 2
            text: ":"
            color: Theme.textDim
        }
        Digits {
            text: Qt.formatTime(clock.date, "mm")
        }
    }

    MText {
        id: date

        anchors.horizontalCenter: parent.horizontalCenter
        y: 110
        height: 16
        text: Strings.lockDate(clock.date)
        size: 12
        caps: true
        color: Theme.textDim
    }
}
