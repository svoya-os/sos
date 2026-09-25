import QtQuick
import qs.core
import qs.components

// Markdown table: Plex Mono 12 inside a bordered 10px-radius block
// (DESIGN.md §5), header row in textFaint, cells in textDim, first column text.
Rectangle {
    id: root

    property var header: []
    property var rows: []
    readonly property int columns: Math.max(root.header.length, root.rows.length > 0 ? root.rows[0].length : 0)

    implicitHeight: col.implicitHeight + 2
    radius: Theme.radiusBlock
    color: "transparent"
    border.width: 1
    border.color: Theme.line
    clip: true

    Column {
        id: col

        x: 1
        y: 1
        width: parent.width - 2

        Repeater {
            model: [root.header].concat(root.rows)

            Item {
                id: tr

                required property var modelData
                required property int index

                width: col.width
                height: Math.max(34, cells.implicitHeight + 16)

                Rectangle {
                    visible: tr.index > 0
                    width: parent.width
                    height: 1
                    color: Theme.line
                }

                Row {
                    id: cells

                    x: 14
                    width: parent.width - 28
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 16

                    Repeater {
                        model: root.columns

                        MText {
                            required property int index

                            width: (cells.width - 16 * (root.columns - 1)) / Math.max(1, root.columns)
                            text: tr.modelData[index] !== undefined ? tr.modelData[index] : ""
                            size: 12
                            wrapMode: Text.WordWrap
                            font.weight: tr.index > 0 && index === 0 ? Font.Medium : Font.Normal
                            color: tr.index === 0 ? Theme.textFaint : (index === 0 ? Theme.text : Theme.textDim)
                        }
                    }
                }
            }
        }
    }
}
