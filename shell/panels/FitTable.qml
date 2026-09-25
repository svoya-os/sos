import QtQuick
import qs.core
import qs.components

// «Will it fit» table from the mockup (```svoya-fit``` blocks from Jackson):
// rows 38px, columns 250 / fill / 64 / 170 with 16px gaps, mono 12. The VRAM
// bar is 6px (surface3 track, accent fill, a 1px capacity mark at the end);
// "warn" rows overflow with warn stripes, "bad" rows get a dotted empty line.
Rectangle {
    id: root

    property var rows: []
    property real capacityGb: Status.gpu && Status.gpu.vramTotalMiB ? Status.gpu.vramTotalMiB / 1024 : 0

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
            model: root.rows

            Item {
                id: row

                required property var modelData
                required property int index
                readonly property string status: modelData.status || "ok"
                readonly property real size: Number(modelData.sizeGb || 0)
                readonly property real fraction: root.capacityGb > 0 && row.size > 0 ? row.size / root.capacityGb : Number(modelData.fraction || 0)

                width: col.width
                height: 38

                Rectangle {
                    visible: row.index > 0
                    width: parent.width
                    height: 1
                    color: Theme.line
                }

                // name + license
                Row {
                    x: 14
                    width: 250
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    clip: true

                    MText {
                        text: row.modelData.name || ""
                        size: 12
                        font.weight: row.status === "bad" ? Font.Normal : Font.Medium
                        color: row.status === "bad" ? Theme.textDim : Theme.text
                    }
                    MText {
                        text: row.modelData.license || ""
                        size: 10.5
                        font.letterSpacing: 0.21
                        color: Theme.textFaint
                    }
                }

                // VRAM bar
                Item {
                    id: bar

                    x: 14 + 250 + 16
                    width: parent.width - x - 16 - 64 - 16 - 170 - 14
                    height: 6
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        anchors.fill: parent
                        visible: row.status !== "bad"
                        radius: 3
                        color: Theme.surface3
                    }

                    Rectangle {
                        visible: row.status === "ok"
                        width: Math.min(1, row.fraction) * parent.width
                        height: parent.height
                        radius: 3
                        color: Theme.accent
                    }

                    // over capacity: warn stripes with a warn border
                    Rectangle {
                        visible: row.status === "warn"
                        anchors.fill: parent
                        radius: 3
                        color: "transparent"
                        border.width: 1
                        border.color: Theme.warn
                        clip: true

                        Canvas {
                            anchors.fill: parent
                            onPaint: {
                                const ctx = getContext("2d");
                                ctx.reset();
                                ctx.strokeStyle = Theme.warn;
                                ctx.lineWidth = 2.2;
                                for (let x = -height; x < width + height; x += 6) {
                                    ctx.beginPath();
                                    ctx.moveTo(x, height);
                                    ctx.lineTo(x + height, 0);
                                    ctx.stroke();
                                }
                            }
                        }
                    }

                    // not usable: dotted hairline
                    Row {
                        visible: row.status === "bad"
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3

                        Repeater {
                            model: Math.max(0, Math.floor(bar.width / 5))

                            Rectangle {
                                width: 2
                                height: 1
                                color: Theme.line
                            }
                        }
                    }

                    // capacity mark
                    Rectangle {
                        visible: row.status !== "bad"
                        x: parent.width
                        y: -4
                        width: 1
                        height: parent.height + 8
                        color: Theme.textFaint
                    }
                }

                MText {
                    x: parent.width - 14 - 170 - 16 - 64
                    width: 64
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignRight
                    text: row.size > 0 ? Fmt.smart(row.size) + " " + Strings.gb : "—"
                    size: 12
                }

                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 7

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: row.status === "ok"
                        glyph: "check"
                        size: 12
                        stroke: 3.2
                        color: Theme.ok
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (row.status === "warn" ? "≈ " : row.status === "bad" ? "× " : "") + (row.modelData.label || (row.status === "ok" ? Strings.fits : ""))
                        size: 12
                        color: row.status === "ok" ? Theme.ok : row.status === "warn" ? Theme.warn : Theme.bad
                    }
                }
            }
        }
    }
}
