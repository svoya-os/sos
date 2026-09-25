import QtQuick
import qs.core

// Segmented choice (Графит / Бумага / Авто). `options`: [{id, label}].
// Arrow keys move the selection when focused.
Rectangle {
    id: root

    property var options: []
    property string current: ""
    signal picked(string key)

    implicitWidth: row.implicitWidth + 4
    implicitHeight: 30
    radius: 8
    color: Theme.surface
    border.width: 1
    border.color: Theme.line
    activeFocusOnTab: true

    function step(d) {
        let i = 0;
        for (let k = 0; k < root.options.length; k++) {
            if (root.options[k].id === root.current)
                i = k;
        }
        const n = (i + d + root.options.length) % root.options.length;
        root.picked(root.options[n].id);
    }

    Keys.onLeftPressed: root.step(-1)
    Keys.onRightPressed: root.step(1)

    Row {
        id: row

        anchors.centerIn: parent
        spacing: 2

        Repeater {
            model: root.options

            Rectangle {
                required property var modelData

                readonly property bool selected: modelData.id === root.current

                width: Math.max(64, label.implicitWidth + 20)
                height: root.height - 4
                radius: 6
                color: selected ? Theme.surface3 : (seg.containsMouse ? Theme.surface2 : "transparent")
                border.width: selected ? 1 : 0
                border.color: Theme.lineStrong

                SText {
                    id: label

                    anchors.centerIn: parent
                    text: modelData.label
                    size: 12.5
                    font.weight: selected ? Font.Medium : Font.Normal
                    color: selected ? Theme.text : Theme.textDim
                }

                MouseArea {
                    id: seg

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(modelData.id)
                }
            }
        }
    }

    FocusRing {
        radiusBase: 8
    }
}
