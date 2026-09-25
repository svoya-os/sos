import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import qs.core

// The wallpaper signal (design/mockups/desktop.html): a faded horizon line at
// 700/900 of the height carrying one Morse «СОС» burst that starts at 1030/1440
// of the width; unit u = 6.5, pulse height 14, 70 px lead-in/out; the tick
// label «··· ——— ···» under it. `s` scales the geometry with the screen.
Item {
    id: root

    property real s: 1
    readonly property real lineY: Math.round(height * 700 / 900) + 0.5
    readonly property real x0: Math.round(width * 1030 / 1440)
    readonly property real u: 6.5 * root.s
    readonly property real ph: 14 * root.s
    readonly property real lead: 70 * root.s

    // Morse geometry, relative to x0 (one entry per rising edge)
    readonly property var burst: {
        const letters = ["...", "---", "..."];
        let x = 0;
        let d = "M 0 " + root.ph;
        for (let li = 0; li < letters.length; li++) {
            for (let si = 0; si < letters[li].length; si++) {
                const w = (letters[li][si] === "." ? 1 : 3) * root.u;
                d += " L " + x + " 0 L " + (x + w) + " 0 L " + (x + w) + " " + root.ph;
                x += w;
                if (si < letters[li].length - 1) {
                    d += " L " + (x + root.u) + " " + root.ph;
                    x += root.u;
                }
            }
            if (li < letters.length - 1) {
                d += " L " + (x + 3 * root.u) + " " + root.ph;
                x += 3 * root.u;
            }
        }
        return { path: d, width: x };
    }

    // faded horizon: transparent -> accent .9 (22%) -> .9 (86%) -> transparent
    Rectangle {
        x: 0
        y: root.lineY - 0.5
        width: root.width
        height: 1
        opacity: Theme.isDark ? 0.22 : 0.4
        gradient: Gradient {
            orientation: Gradient.Horizontal

            GradientStop {
                position: 0
                color: Theme.alpha(Theme.accent, 0)
            }
            GradientStop {
                position: 0.22
                color: Theme.alpha(Theme.accent, 0.9)
            }
            GradientStop {
                position: 0.86
                color: Theme.alpha(Theme.accent, 0.9)
            }
            GradientStop {
                position: 1
                color: Theme.alpha(Theme.accent, 0)
            }
        }
    }

    // the burst; its ends fade over the lead-in/out (gradient 0 -> 18% -> 82% -> 100%)
    Item {
        id: pulse

        readonly property real total: root.burst.width + 2 * root.lead
        readonly property real fadeLen: 0.18 * pulse.total

        x: root.x0 - root.lead
        y: root.lineY - root.ph
        width: pulse.total
        height: root.ph + 2
        opacity: 0.9
        layer.enabled: Theme.glow
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.alpha(Theme.accent, 0.45)
            shadowBlur: 0.25
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }

        Rectangle {
            x: 0
            y: root.ph - 0.7
            width: root.lead
            height: 1.4
            gradient: Gradient {
                orientation: Gradient.Horizontal

                GradientStop {
                    position: 0
                    color: Theme.alpha(Theme.accent, 0)
                }
                GradientStop {
                    position: Math.min(1, pulse.fadeLen / root.lead)
                    color: Theme.accent
                }
            }
        }

        Shape {
            x: root.lead
            y: 0
            width: root.burst.width
            height: root.ph + 1
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: Theme.accent
                strokeWidth: 1.4
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin

                PathSvg {
                    path: root.burst.path
                }
            }
        }

        Rectangle {
            x: root.lead + root.burst.width
            y: root.ph - 0.7
            width: root.lead
            height: 1.4
            gradient: Gradient {
                orientation: Gradient.Horizontal

                GradientStop {
                    position: Math.max(0, 1 - pulse.fadeLen / root.lead)
                    color: Theme.accent
                }
                GradientStop {
                    position: 1
                    color: Theme.alpha(Theme.accent, 0)
                }
            }
        }
    }

    MText {
        x: root.x0
        y: root.lineY + 26 - 10.25 // baseline at +26 (Plex Mono ascent ≈ 1.025em)
        text: Strings.morse
        size: 10
        font.letterSpacing: 3
        color: Theme.textFaint
        opacity: 0.8
    }
}
