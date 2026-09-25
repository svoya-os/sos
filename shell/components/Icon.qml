import QtQuick
import QtQuick.Shapes
import qs.core

// Line icon from the registry (core/Icons.qml, generated from assets/icons).
// Drawn with QtQuick.Shapes so strokes follow the theme color exactly.
// `stroke` is in the 24-unit viewBox (1.5 like the mockup: at 15px that is
// a ~0.94px hairline; at 20px 1.25px).
Item {
    id: root

    property string glyph: "circle-alert"
    property color color: Theme.textDim
    property real size: 15
    property real stroke: 1.5

    readonly property var def: Icons.get(root.glyph)

    implicitWidth: root.size
    implicitHeight: root.size

    Shape {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: root.color
            strokeWidth: root.stroke
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin

            PathSvg {
                path: root.def.s
            }
        }

        ShapePath {
            strokeColor: "transparent"
            strokeWidth: 0
            fillColor: root.def.f.length > 0 ? root.color : "transparent"

            PathSvg {
                path: root.def.f.length > 0 ? root.def.f : "M0 0"
            }
        }
    }
}
