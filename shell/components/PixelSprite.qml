import QtQuick
import qs.core

// Pixel-art sprite: a grid of one-character keys ("." = transparent) and a key → color map,
// drawn at an integer scale with no smoothing (DESIGN §13: 32 · 64 · 128 · 192 px for a
// 32-pixel sprite). Horizontal runs of one key become one rectangle (≈ 300 per frame).
// Repaints only when the grid, the colors or the scale change.
Canvas {
    id: root

    property var grid: null          // [32 strings]
    property var colors: ({})        // key -> "#rrggbb"
    property int pixel: 1            // integer scale: one sprite pixel = pixel × pixel

    readonly property int cells: root.grid ? root.grid.length : 32

    implicitWidth: root.cells * root.pixel
    implicitHeight: root.cells * root.pixel
    width: root.implicitWidth
    height: root.implicitHeight
    renderStrategy: Canvas.Cooperative
    smooth: false
    antialiasing: false

    onGridChanged: root.requestPaint()
    onColorsChanged: root.requestPaint()
    onPixelChanged: root.requestPaint()
    onAvailableChanged: root.requestPaint()

    onPaint: {
        const ctx = root.getContext("2d");
        ctx.clearRect(0, 0, root.width, root.height);
        const g = root.grid;
        if (!g)
            return;
        const s = root.pixel;
        const pal = root.colors || {};
        for (let y = 0; y < g.length; y++) {
            const row = g[y];
            let x = 0;
            while (x < row.length) {
                const k = row[x];
                let e = x + 1;
                while (e < row.length && row[e] === k)
                    e++;
                if (k !== "." && pal[k]) {
                    ctx.fillStyle = pal[k];
                    ctx.fillRect(x * s, y * s, (e - x) * s, s);
                }
                x = e;
            }
        }
    }
}
