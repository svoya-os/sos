import QtQuick
import qs.core
import qs.components

// "Super Shift S" -> [Super] [Shift] [S]; "Super Q | Alt F4" -> [Super] [Q] / [Alt] [F4]
Row {
    id: combo

    property string keys: ""

    spacing: 4

    Repeater {
        model: combo.keys.split("|").map(k => k.trim()).filter(k => k.length > 0)

        Row {
            id: group

            required property var modelData
            required property int index

            spacing: 4

            MText {
                anchors.verticalCenter: parent.verticalCenter
                visible: group.index > 0
                text: "/"
                size: 11
                color: Theme.textFaint
            }

            Repeater {
                model: group.modelData.split(" ").filter(k => k.length > 0)

                Keycap {
                    required property var modelData

                    text: modelData
                }
            }
        }
    }
}
