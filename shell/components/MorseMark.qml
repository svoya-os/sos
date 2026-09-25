import QtQuick
import qs.core

// The mark: Morse «СОС» ··· ——— ··· (same in Russian and international Morse).
// Geometry from design/mockups/desktop.html: dots 3.2×3.2, dashes 8×3.2,
// radius 1.6, 2.4 between symbols, +3.2 between letters. Neutral by default (DESIGN §11–§12):
// the ——— light up in the accent only when `lit` (the bar, while Jackson listens or works).
Item {
    id: root

    property real unit: 1            // scale (1 = bar size, 3.2 px high)
    property color color: Theme.text
    property color accent: Theme.accent
    property bool lit: false

    readonly property real h: 3.2 * root.unit
    // x positions of the 9 symbols and whether each is a dash
    readonly property var symbols: {
        const out = [];
        const letters = ["...", "---", "..."];
        let x = 0;
        for (let li = 0; li < letters.length; li++) {
            for (let si = 0; si < letters[li].length; si++) {
                const dash = letters[li][si] === "-";
                out.push({ x: x, w: dash ? 8 : 3.2, letter: li });
                x += (dash ? 8 : 3.2) + 2.4;
            }
            x += 3.2;
        }
        return out;
    }

    implicitWidth: 68.8 * root.unit   // visual extent (last dot ends at 68.8)
    implicitHeight: root.h

    Repeater {
        model: root.symbols

        Rectangle {
            required property var modelData

            x: modelData.x * root.unit
            y: 0
            width: modelData.w * root.unit
            height: root.h
            radius: root.h / 2
            color: modelData.letter === 1 && root.lit ? root.accent : root.color

            Behavior on color {
                ColorAnimation {
                    duration: Theme.slow
                    easing.type: Theme.easing
                }
            }
            antialiasing: true
        }
    }
}
