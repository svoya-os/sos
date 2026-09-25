import QtQuick
import qs.core
import qs.components

// "Super Shift S" -> [Super] [Shift] [S]
Row {
    id: combo

    property string keys: ""

    spacing: 4

    Repeater {
        model: combo.keys.split(" ").filter(k => k.length > 0)

        Keycap {
            required property var modelData

            text: modelData
        }
    }
}
