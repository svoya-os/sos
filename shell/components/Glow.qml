import QtQuick
import QtQuick.Shapes

// Elliptical radial glow, like CSS radial-gradient(RXpx RYpx at X Y, color,
// transparent STOP). A circle of radius rx scaled vertically to ry.
Item {
    id: root

    property real cx: 0
    property real cy: 0
    property real rx: 100
    property real ry: 100
    property color color: "white"
    property real stop: 0.62

    x: root.cx - root.rx
    y: root.cy - root.rx
    width: root.rx * 2
    height: root.rx * 2
    transform: Scale {
        origin.x: root.rx
        origin.y: root.rx
        yScale: root.rx > 0 ? root.ry / root.rx : 1
    }

    Shape {
        anchors.fill: parent

        ShapePath {
            strokeColor: "transparent"
            strokeWidth: 0
            fillGradient: RadialGradient {
                centerX: root.rx
                centerY: root.rx
                centerRadius: root.rx
                focalX: root.rx
                focalY: root.rx

                GradientStop {
                    position: 0
                    color: root.color
                }
                GradientStop {
                    position: root.stop
                    color: Qt.rgba(root.color.r, root.color.g, root.color.b, 0)
                }
            }
            startX: 0
            startY: 0

            PathLine {
                x: root.width
                y: 0
            }
            PathLine {
                x: root.width
                y: root.height
            }
            PathLine {
                x: 0
                y: root.height
            }
            PathLine {
                x: 0
                y: 0
            }
        }
    }
}
