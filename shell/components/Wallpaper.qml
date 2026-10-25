import QtQuick
import qs.core

// The SOS wallpaper, drawn live from the theme (design/mockups/desktop.css):
// gradient + soft glows, the horizon line with one Morse «СОС» burst, grain,
// and the colophon «SOS 26.10 · первый сигнал». Paper adds the 22px dot grid,
// Phosphor adds scanlines. With the symbol layer (Theme.symbols) a live ASCII scene takes the
// burst's place (Settings.asciiScene: the planet, Jackson's eye or the rain; it moves only while
// `live`, the desktop's call). A configured image (Settings.wallpaper) replaces it all.
// Composition is defined on a 1440×900 canvas and scaled with the screen.
Item {
    id: root

    property bool colophon: true
    property bool showSignal: true
    // the soft glows follow the accent on the desktop and the lock screen; the greeter keeps
    // them neutral (DESIGN §12: before login the accent is only the caret and the burst)
    property bool ambient: true
    readonly property color glowTint: root.ambient ? Theme.accent : Theme.text
    readonly property real glowGain: root.ambient ? 1 : 0.4
    property string image: Settings.wallpaper
    // the desktop sets it while the wallpaper can be seen (an empty workspace, Super+D); the lock
    // screen and the greeter leave it off and get no scene at all
    property bool live: false
    property bool ascii: false
    readonly property string scene: root.ascii && Theme.symbols && !root.useImage && ["planets", "eye", "rain"].indexOf(Settings.asciiScene) >= 0 ? Settings.asciiScene : ""

    readonly property real s: Math.max(1, Math.min(1.6, Math.max(width / 1440, height / 900)))
    readonly property string recipe: {
        const id = Theme.themeId;
        if (id === "graphite" || id === "paper" || id === "phosphor")
            return id;
        return Theme.isDark ? "graphite" : "paper";
    }
    readonly property bool useImage: root.image.length > 0 && picture.status !== Image.Error

    clip: true

    Rectangle {
        anchors.fill: parent
        color: Theme.wall
        gradient: Gradient {
            GradientStop {
                position: 0
                color: root.recipe === "graphite" ? (Theme.themeId === "graphite" ? "#0f1012" : Qt.lighter(Theme.wall, 1.2)) : root.recipe === "paper" ? (Theme.themeId === "paper" ? "#edeae3" : Qt.lighter(Theme.wall, 1.02)) : Theme.wall
            }
            GradientStop {
                position: 1
                color: root.recipe === "graphite" ? (Theme.themeId === "graphite" ? "#0b0c0e" : Theme.wall) : root.recipe === "paper" ? (Theme.themeId === "paper" ? "#e6e3da" : Qt.darker(Theme.wall, 1.02)) : Theme.wall
            }
        }
    }

    // Graphite: amber from the top-left, a cold hint from the bottom-right.
    Glow {
        visible: root.recipe === "graphite"
        cx: root.width * 0.12
        cy: -root.height * 0.06
        rx: 1100 * root.s
        ry: 620 * root.s
        color: Theme.alpha(root.glowTint, 0.075 * root.glowGain)
        stop: 0.62
    }
    Glow {
        visible: root.recipe === "graphite"
        cx: root.width * 1.04
        cy: root.height * 1.08
        rx: 900 * root.s
        ry: 700 * root.s
        color: Theme.alpha(Theme.cloud, 0.045)
        stop: 0.60
    }

    // Phosphor: a green glow rising from below and a faint one top-left.
    Glow {
        visible: root.recipe === "phosphor"
        cx: root.width * 0.5
        cy: root.height * 1.18
        rx: 1200 * root.s
        ry: 520 * root.s
        color: Theme.alpha(root.glowTint, 0.10 * root.glowGain)
        stop: 0.65
    }
    Glow {
        visible: root.recipe === "phosphor"
        cx: 0
        cy: 0
        rx: 900 * root.s
        ry: 500 * root.s
        color: Theme.alpha(root.glowTint, 0.035 * root.glowGain)
        stop: 0.60
    }

    // Paper: 22px dot grid (dots at multiples of 22px, as the CSS offset 11/11).
    Image {
        visible: root.recipe === "paper"
        x: -11
        y: -11
        width: root.width + 22
        height: root.height + 22
        source: Theme.asset("textures/dots.png")
        fillMode: Image.Tile
        smooth: false
    }

    SignalBurst {
        anchors.fill: parent
        visible: root.showSignal && root.scene.length === 0
        s: root.s
    }

    Loader {
        anchors.fill: parent
        active: root.scene.length > 0
        sourceComponent: AsciiView {
            scene: root.scene
            rows: 48
            fps: root.scene === "rain" ? 20 : 10        // drops jump at 10; the rain is the cheapest scene
            running: root.live && !Theme.reduceMotion && !Hypr.gaming
            opacity: 0.6
        }
    }

    // Grain (dark: faint symmetric speckle that also dithers the glows;
    // light: multiply-like specks). Theme.grain is the opacity token.
    Image {
        anchors.fill: parent
        source: Theme.asset(Theme.isDark ? "textures/grain-dark.png" : "textures/grain-light.png")
        fillMode: Image.Tile
        opacity: Theme.grain
        smooth: false
    }

    // Phosphor scanlines: 1px of black at 22% every 3px.
    Image {
        anchors.fill: parent
        visible: Theme.scanlines
        source: Theme.asset("textures/scanlines.png")
        fillMode: Image.Tile
        smooth: false
    }

    Image {
        id: picture

        anchors.fill: parent
        visible: root.useImage
        // encodeURI: Jackson's pictures have spaces and Cyrillic in their names («… кот в шляпе.png»)
        source: root.image.length > 0 ? "file://" + encodeURI(root.image).replace(/#/g, "%23").replace(/\?/g, "%3F") : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        sourceSize.width: root.width
        sourceSize.height: root.height
    }

    // colophon: right 28, bottom 22; Plex Mono 10/1.5, +0.14em, uppercase
    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 28
        anchors.bottomMargin: 22
        visible: root.colophon && !root.useImage
        spacing: 0

        MText {
            text: Strings.osName + " "
            size: 10
            caps: true
            font.weight: Font.Medium
            color: Theme.textDim
        }
        MText {
            text: Sys.osVersion + " · " + Strings.codename
            size: 10
            caps: true
            color: Theme.textFaint
        }
    }
}
