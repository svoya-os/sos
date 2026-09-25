import QtQuick
import qs.core

// A color swatch (DESIGN §10, mockups control-center-look / setup-look / jackson-customize):
// a circle with a hairline edge; `second` splits it diagonally (the «Сигнал» accent: its night
// and day colors); `rainbow` draws the «Свой…» swatch (a color ring around the chosen color,
// or a «+» when there is none yet). The selected one gets a neutral ring: 1.5px `text` with a
// 2px gap (never the accent, §11). Hover grows it a little. Keyboard: Enter/Space pick it.
Item {
    id: root

    property color color: "transparent"
    property color second: "transparent"     // split: top-left = color, bottom-right = second
    property bool split: false
    property bool rainbow: false             // «Свой…»
    property bool empty: false               // rainbow without a color yet: a «+»
    property bool selected: false
    property real size: 28
    property string label: ""                // accessible name (and tooltip-free label below, if any)

    signal picked

    readonly property bool hovered: mouse.containsMouse

    implicitWidth: root.size + 8
    implicitHeight: root.size + 8
    activeFocusOnTab: true
    Accessible.role: Accessible.RadioButton
    Accessible.name: root.label
    Keys.onReturnPressed: root.picked()
    Keys.onSpacePressed: root.picked()

    // selection ring: 1.5px text, 2px gap
    Rectangle {
        anchors.centerIn: parent
        width: root.size + 7
        height: root.size + 7
        radius: width / 2
        visible: root.selected
        color: "transparent"
        border.width: 1.5
        border.color: Theme.selected
        antialiasing: true
    }

    Item {
        id: disc

        anchors.centerIn: parent
        width: root.size
        height: root.size
        scale: root.hovered && !root.selected ? 1.08 : 1

        Behavior on scale {
            NumberAnimation {
                duration: Theme.fast
                easing.type: Theme.easing
            }
        }

        // plain color
        Rectangle {
            anchors.fill: parent
            visible: !root.split && !root.rainbow
            radius: width / 2
            color: root.color
            border.width: 1
            border.color: Qt.rgba(0.5, 0.5, 0.5, 0.3)
            antialiasing: true
        }

        // split / rainbow: drawn once per change
        Canvas {
            id: art

            anchors.fill: parent
            visible: root.split || root.rainbow
            antialiasing: true
            renderStrategy: Canvas.Cooperative

            onPaint: {
                const ctx = art.getContext("2d");
                const w = art.width, c = w / 2, r = w / 2;
                ctx.clearRect(0, 0, w, w);
                if (root.split) {
                    ctx.fillStyle = String(root.color);
                    ctx.beginPath();
                    ctx.arc(c, c, r, 0, 2 * Math.PI);
                    ctx.fill();
                    ctx.fillStyle = String(root.second);
                    ctx.beginPath();
                    ctx.arc(c, c, r, -Math.PI / 4, 3 * Math.PI / 4);
                    ctx.closePath();
                    ctx.fill();
                } else {
                    const g = ctx.createConicalGradient(c, c, Math.PI * 0.9);
                    const stops = ["#ff82b2", "#bba4ff", "#62d4f2", "#5cf08f", "#ffb547", "#ff82b2"];
                    for (let i = 0; i < stops.length; i++)
                        g.addColorStop(i / (stops.length - 1), stops[i]);
                    ctx.fillStyle = g;
                    ctx.beginPath();
                    ctx.arc(c, c, r, 0, 2 * Math.PI);
                    ctx.fill();
                    // inner disc: the chosen color, or the panel color under a «+»
                    ctx.fillStyle = root.empty ? String(Theme.surface2) : String(root.color);
                    ctx.beginPath();
                    ctx.arc(c, c, r - Math.max(3, w * 0.18), 0, 2 * Math.PI);
                    ctx.fill();
                }
                ctx.strokeStyle = "rgba(128,128,128,0.3)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(c, c, r - 0.5, 0, 2 * Math.PI);
                ctx.stroke();
            }

            Connections {
                target: root

                function onColorChanged() {
                    art.requestPaint();
                }
                function onSecondChanged() {
                    art.requestPaint();
                }
                function onEmptyChanged() {
                    art.requestPaint();
                }
                function onSplitChanged() {
                    art.requestPaint();
                }
                function onRainbowChanged() {
                    art.requestPaint();
                }
            }

            Connections {
                target: Theme

                function onSurface2Changed() {
                    if (root.rainbow && root.empty)
                        art.requestPaint();
                }
            }
        }

        Icon {
            anchors.centerIn: parent
            visible: root.rainbow && root.empty
            glyph: "plus"
            size: Math.round(root.size * 0.5)
            stroke: 2
            color: Theme.textDim
        }
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }

    FocusRing {
        radiusBase: root.width / 2
    }
}
