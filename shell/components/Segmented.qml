import QtQuick
import qs.core

// Segmented choice (Графит / Бумага / Авто / Фосфор). `options`: [{id, label, swatch?}] where
// `swatch` is an optional theme dot: {fill, edge, inner?, half?} (half = the right half's color).
// Segments share the width equally when the control is wider than its content. The selected
// segment is neutral: surface3 + lineStrong edge + `text` label (DESIGN §11).
// Arrow keys move the selection when focused.
Rectangle {
    id: root

    property var options: []
    property string current: ""
    property real fontSize: 12.5
    signal picked(string key)

    // the width without stretching (from each segment's own content, so no binding loop)
    readonly property real naturalWidth: {
        let w = 4 + row.spacing * Math.max(0, rep.count - 1);
        for (let i = 0; i < rep.count; i++) {
            const it = rep.itemAt(i);
            if (it)
                w += it.natural;
        }
        return w;
    }

    implicitWidth: root.naturalWidth
    implicitHeight: 30
    radius: 8
    color: Theme.surface
    border.width: 1
    border.color: Theme.line
    activeFocusOnTab: true
    Accessible.role: Accessible.PageTabList

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
            id: rep

            model: root.options

            Rectangle {
                id: seg

                required property var modelData
                required property int index

                readonly property bool selected: modelData.id === root.current
                readonly property real natural: Math.max(64, content.implicitWidth + 20)
                readonly property real share: (root.width - 4 - row.spacing * (rep.count - 1)) / Math.max(1, rep.count)

                implicitWidth: seg.natural
                width: root.width > root.naturalWidth + 1 ? Math.max(seg.natural, seg.share) : seg.natural
                height: root.height - 4
                radius: 6
                color: seg.selected ? Theme.surface3 : (segMouse.containsMouse ? Theme.surface2 : "transparent")
                border.width: seg.selected ? 1 : 0
                border.color: Theme.lineStrong
                Accessible.role: Accessible.PageTab
                Accessible.name: seg.modelData.label

                Row {
                    id: content

                    anchors.centerIn: parent
                    spacing: 6

                    // theme dot: fill + edge, optional inner dot (Phosphor) or right half (Auto)
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: seg.modelData.swatch !== undefined
                        width: 12
                        height: 12
                        radius: 6
                        color: seg.modelData.swatch ? seg.modelData.swatch.fill : "transparent"
                        border.width: 1
                        border.color: seg.modelData.swatch ? seg.modelData.swatch.edge : "transparent"
                        antialiasing: true
                        gradient: seg.modelData.swatch && seg.modelData.swatch.half ? halfGradient : null

                        Gradient {
                            id: halfGradient

                            orientation: Gradient.Horizontal

                            GradientStop {
                                position: 0.5
                                color: seg.modelData.swatch ? seg.modelData.swatch.fill : "transparent"
                            }
                            GradientStop {
                                position: 0.501
                                color: seg.modelData.swatch && seg.modelData.swatch.half ? seg.modelData.swatch.half : "transparent"
                            }
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            visible: seg.modelData.swatch !== undefined && seg.modelData.swatch.inner !== undefined
                            width: 4
                            height: 4
                            radius: 2
                            color: seg.modelData.swatch && seg.modelData.swatch.inner ? seg.modelData.swatch.inner : "transparent"
                        }
                    }

                    SText {
                        id: label

                        anchors.verticalCenter: parent.verticalCenter
                        text: seg.modelData.label
                        size: root.fontSize
                        font.weight: seg.selected ? Font.Medium : Font.Normal
                        color: seg.selected ? Theme.text : Theme.textDim
                    }
                }

                MouseArea {
                    id: segMouse

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(seg.modelData.id)
                }
            }
        }
    }

    FocusRing {
        radiusBase: 8
    }
}
