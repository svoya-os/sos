import QtQuick
import qs.core
import "ascii.js" as Ascii

// SOS ASCII in the shell (components/ascii.js, the twin of `sos eye` / `sos art`): an effect drawn
// as text. Three Text layers (grey noise, phosphor, the alive pink) are laid out once per frame each
// and drawn by the scene graph; nothing is rasterized by hand. Cells are twice as tall as wide, like
// the terminal the effects were made for, and the grid is about `rows` rows tall on any screen, so a
// frame costs the same on 1080p and on 4K.
//
// scene:  "eye"     Jackson's eye (mood: idle | thinking | listening); the pupil follows the pointer
//         "story"   the short film (it looks closer: Jackson is inside); `finished` at the end
//         "planets" the screensaver planet (`sos art planets`)
//         "rain"    night rain that writes the signal into the water (`sos art rain`)
//         "logo"    the letters SOS out of noise, the boot line and the signal (`sos art logo`)
//         "heart"   a beating heart and its monitor (`sos art heart`)
//         "saver"   Jackson, standing in `from`, turns into his eye; the film every few minutes
//         "jackson" Jackson himself in symbols (mood = his pose), `cols` wide; drawn only on change
Item {
    id: root

    property string scene: "eye"
    property string mood: "idle"
    property var look: Avatar.look
    property rect from: Qt.rect(0, 0, 0, 0)     // saver: where Jackson stands in this item, pixels
    property bool running: true                 // false: frozen on the last frame
    property real fps: 24
    property int rows: 56                       // grid height in cells (not for "jackson")
    property int cols: 32                       // "jackson": his width in cells (even)
    property bool follow: true                  // the eye looks at the pointer over this item
    property bool night: false
    property color fg: Theme.accent
    property color noise: Theme.textFaint
    property color alive: Theme.isDark ? "#ff2e88" : "#d6246e"

    signal finished

    readonly property real cellW: root.scene === "jackson" ? root.width / Math.max(2, root.cols) : root.height / Math.max(4, root.rows) / 2
    readonly property int gridW: root.scene === "jackson" ? root.cols : Math.max(1, Math.floor(root.width / Math.max(1, root.cellW)))
    readonly property int gridH: root.scene === "jackson" ? Math.floor(root.cols / 2) : Math.max(1, Math.floor(root.height / Math.max(1, 2 * root.cellW)))
    // the mono font's advance per pixel of size (about 0.6); `ref.font` makes the binding follow the font
    readonly property real ratio: {
        ref.font;
        return ref.advanceWidth("M") / 100;
    }
    readonly property bool ready: root.width > 0 && root.height > 0 && root.cellW > 1 && root.ratio > 0

    property var layers: ["", "", "", ""]
    property var fx: null
    property real t0: Date.now()
    property real cost: 0                        // ms per frame, smoothed: the timer slows down to keep JS light
    property bool ended: false

    function now() {
        return (Date.now() - root.t0) / 1000;
    }

    function trigger(kind) {
        if (root.fx && root.fx.trigger)
            root.fx.trigger(kind, root.now());
    }

    function restart() {
        root.t0 = Date.now();
        root.ended = false;
        root.rebuild();
    }

    function rebuild() {
        root.fx = null;
        if (!root.ready || root.scene === "jackson") {
            root.paint();
            return;
        }
        const look = root.look || {};
        const sprite = Avatar.dataFor(look.character || "imp");
        const night = root.night;
        if (root.scene === "planets") {
            root.fx = new Ascii.AsciiPlanets({ hud: false });       // no "Q QUIT" frame: nothing here takes keys
        } else if (root.scene === "rain") {
            root.fx = new Ascii.AsciiRain({ hud: false });
        } else if (root.scene === "logo") {
            root.fx = new Ascii.AsciiLogo({ hud: false });
        } else if (root.scene === "heart") {
            root.fx = new Ascii.AsciiHeart({ hud: false });
        } else if (root.scene === "story") {
            root.fx = new Ascii.AsciiEye({ story: true, night: night, sprite: sprite, look: look });
        } else if (root.scene === "saver") {
            const has = root.from.width > 0;
            const f = has ? {
                x: Math.round((root.from.x - grid.x) / root.cellW),
                y: Math.round((root.from.y - grid.y) / (2 * root.cellW)),
                cols: Math.round(root.from.width / root.cellW)
            } : null;
            root.fx = new Ascii.AsciiSaver({ sprite: sprite, look: look, night: night, from: f });
        } else {
            root.fx = new Ascii.AsciiEye({ state: root.mood, hud: false, night: night, sprite: sprite, look: look });
        }
        root.paint();
    }

    function paint() {
        if (!root.ready)
            return;
        const start = Date.now();
        const cv = Ascii.asciiCanvas(root.gridW, root.gridH);
        if (root.scene === "jackson") {
            const look = root.look || {};
            const sprite = Avatar.dataFor(look.character || "imp");
            if (sprite)
                Ascii.asciiJackson(sprite, look, root.mood, root.gridW).forEach(e => Ascii.asciiPut(cv, e[0], e[1], e[2], e[3]));
        } else if (root.fx) {
            const t = root.now();
            const loop = ["eye", "planets", "rain", "logo", "heart"].indexOf(root.scene) >= 0 ? t % 3600 : t;
            if (root.scene === "eye" && root.fx.mode !== root.mood && ["idle", "thinking", "listening"].indexOf(root.mood) >= 0)
                root.fx.mode = root.mood;
            if (root.fx.w !== cv.w || root.fx.h !== cv.h)
                root.fx.resize(cv.w, cv.h);
            root.fx.draw(cv, loop);
            if (root.fx.duration && t >= root.fx.duration && !root.ended) {
                root.ended = true;
                root.finished();
            }
        }
        root.layers = Ascii.asciiLayers(cv);
        root.cost = root.cost * 0.9 + (Date.now() - start) * 0.1;
    }

    onSceneChanged: root.restart()
    onLookChanged: root.rebuild()
    onFromChanged: if (root.scene === "saver") root.rebuild()
    onNightChanged: root.rebuild()
    onMoodChanged: if (root.scene === "jackson" || !root.running) root.paint()
    onGridWChanged: root.rebuild()
    onGridHChanged: root.rebuild()
    onReadyChanged: root.rebuild()
    Component.onCompleted: root.rebuild()

    Timer {
        // never more than about a third of a core: a slow frame stretches the interval
        interval: Math.max(1000 / Math.max(1, root.fps), root.cost * 3)
        repeat: true
        running: root.running && root.visible && root.ready && root.scene !== "jackson" && root.fx !== null
        onTriggered: root.paint()
    }

    FontMetrics {
        id: ref

        font.family: Theme.mono
        font.pixelSize: 100
    }
    FontMetrics {
        id: fm

        font.family: Theme.mono
        font.pixelSize: grid.px
    }

    // the grid, centered; drawn at a whole pixel size and scaled to the exact cell
    Item {
        id: grid

        readonly property int px: Math.max(4, Math.round(root.cellW / Math.max(0.01, root.ratio)))
        readonly property real adv: {
            fm.font;
            return Math.max(1, fm.advanceWidth("M"));
        }

        x: Math.floor((root.width - root.gridW * root.cellW) / 2)
        y: Math.floor((root.height - root.gridH * 2 * root.cellW) / 2)
        width: root.gridW * grid.adv
        height: root.gridH * 2 * grid.adv
        scale: root.cellW / grid.adv
        transformOrigin: Item.TopLeft

        Repeater {
            model: [3, 1, 2]    // noise under phosphor under the alive pink

            Text {
                required property int modelData

                text: root.layers[modelData] || ""
                color: modelData === 1 ? root.fg : modelData === 2 ? root.alive : root.noise
                font.family: Theme.mono
                font.pixelSize: grid.px
                font.kerning: false
                font.preferShaping: false
                lineHeightMode: Text.FixedHeight
                lineHeight: 2 * grid.adv
                textFormat: Text.PlainText
                wrapMode: Text.NoWrap
                renderType: Text.QtRendering
            }
        }
    }

    HoverHandler {
        enabled: root.follow && ["eye", "story", "saver"].indexOf(root.scene) >= 0
        onPointChanged: {
            if (root.fx && root.fx.pointer && hovered)
                root.fx.pointer(Math.floor((point.position.x - grid.x) / root.cellW), Math.floor((point.position.y - grid.y) / (2 * root.cellW)), root.scene === "saver" ? root.now() : root.now() % 3600);
        }
    }
}
