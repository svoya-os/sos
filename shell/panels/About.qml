import QtQuick
import qs.core
import qs.components

// About (СОС menu): the mark, the name, version and codename, the hardware
// line from `sos status`, the promise and licenses.
PanelFrame {
    id: root

    width: 460
    implicitHeight: col.implicitHeight

    onShownChanged: {
        if (root.shown)
            Qt.callLater(() => keys.forceActiveFocus());
    }

    Item {
        id: keys

        focus: true
        Keys.onEscapePressed: Ui.hide()
        Keys.onReturnPressed: Ui.hide()
    }

    Column {
        id: col

        width: parent.width
        topPadding: 28
        bottomPadding: 24
        spacing: 14

        MorseMark {
            anchors.horizontalCenter: parent.horizontalCenter
            unit: 2
        }

        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 4

            SText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Strings.osName + " " + Sys.osVersion
                size: 22
                font.weight: Font.Medium
            }

            SText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Strings.osNameLocal
                size: 13
                color: Theme.textDim
            }

            MText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "«" + Strings.codename + "»"
                size: 11
                caps: true
                color: Theme.textFaint
            }
        }

        Divider {
            width: parent.width - 48
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Column {
            x: 24
            width: parent.width - 48
            spacing: 6

            Row {
                spacing: 12
                visible: Status.gpu !== null

                MText {
                    width: 80
                    text: Strings.gpu
                    size: 11
                    color: Theme.textFaint
                }
                MText {
                    text: Status.gpu ? (Status.gpu.name || "") + (Status.gpu.driver ? " · " + Strings.driver + " " + Status.gpu.driver : "") : ""
                    size: 11
                    color: Theme.textDim
                }
            }

            Row {
                spacing: 12
                visible: Jackson.connected

                MText {
                    width: 80
                    text: Strings.jackson
                    size: 11
                    color: Theme.textFaint
                }
                MText {
                    text: (Jackson.daemonVersion.length > 0 ? Jackson.daemonVersion : "") + (Jackson.shownRoute && Jackson.shownRoute.model ? " · " + Jackson.shownRoute.model : "")
                    size: 11
                    color: Theme.textDim
                }
            }

            SText {
                width: parent.width
                topPadding: 6
                wrapMode: Text.WordWrap
                text: Strings.promise
                size: 13
                color: Theme.text
            }

            MText {
                width: parent.width
                wrapMode: Text.WordWrap
                text: Strings.licenses
                size: 10.5
                color: Theme.textFaint
                lineHeight: 1.4
            }
        }
    }
}
