import QtQuick
import qs.core
import qs.components

// One tool call Jackson makes: state glyph · name · summary (mono 11).
Row {
    id: root

    property var call: ({})
    readonly property string state: root.call.state || "running"

    spacing: 8

    Item {
        width: 12
        height: 14

        Dot {
            anchors.centerIn: parent
            visible: root.state === "running"
            color: Theme.accent
            SequentialAnimation on opacity {
                running: root.state === "running" && !Theme.reduceMotion
                loops: Animation.Infinite
                NumberAnimation {
                    to: 0.3
                    duration: 600
                }
                NumberAnimation {
                    to: 1
                    duration: 600
                }
            }
        }

        Icon {
            anchors.centerIn: parent
            visible: root.state !== "running"
            glyph: root.state === "done" ? "check" : "x"
            size: 12
            stroke: 2.4
            color: root.state === "done" ? Theme.ok : Theme.bad
        }
    }

    MText {
        text: root.call.name || ""
        size: 11
        color: Theme.textDim
    }

    MText {
        width: 520
        text: root.call.summary || ""
        size: 11
        color: Theme.textFaint
        elide: Text.ElideRight
    }
}
