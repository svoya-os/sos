import QtQuick
import qs.core
import "Sprite.js" as Sprite

// Jackson's face (DESIGN §13): the pixel mascot from assets/jackson/<character>.json, drawn by
// PixelSprite at an integer scale (32 · 64 · 128 · 192 px) on a surface3 rounded square.
// The look comes from ~/.config/svoya/avatar.json (Avatar); the outfit follows the accent
// unless pinned, the detail (horns, LEDs, drawstrings) is the accent itself.
//
// State: Jackson's scope state and mood → idle (blinks every ~4–6 s) · listening · thinking
// (thinking/working) · talking (speaking; two frames at 140 ms) · happy (the beat after an
// answer) · error. `forceAnim` pins one (customizer preview); reduce motion shows frame 0 only.
// Without sprite data the oscilloscope trace stands in. Right-click → «Настроить Джексона».
Item {
    id: root

    property int size: 32                  // box, px; the sprite scale is floor(size / 32)
    property bool backing: true            // surface3 rounded square behind the sprite
    // scope state (override for previews). With `forceAnim` set, Jackson is never touched (the
    // wizard shows the mascot without starting a second connection to jacksond).
    property string mode: root.forceAnim.length > 0 ? "idle" : Jackson.mode
    property bool live: true               // animate (blink, talk)
    property string forceAnim: ""          // idle | listening | thinking | talking | happy | error
    property var look: Avatar.look         // a pending look (customizer, wizard)
    property bool menu: true               // right-click menu
    property real scopeWidth: 92           // fallback trace size
    property real scopeHeight: 22

    readonly property var spriteData: Avatar.dataFor(root.look ? root.look.character : "imp")
    readonly property bool hasSprite: root.spriteData !== null
    readonly property int pixelScale: Math.max(1, Math.floor(root.size / (root.spriteData && root.spriteData.size ? root.spriteData.size : 32)))

    // the animation for the current state
    property real now: Date.now()
    readonly property string anim: {
        if (root.forceAnim.length > 0)
            return root.forceAnim;
        const m = root.mode;
        const mood = Jackson.mood;
        if (Jackson.happyUntil > root.now)
            return "happy";
        if (m === "error" || mood === "sorry")
            return "error";
        if (m === "listening")
            return "listening";
        if (m === "speaking" || mood === "talking")
            return "talking";
        if (m === "thinking" || m === "working" || mood === "busy" || mood === "thinking" || mood === "asking")
            return "thinking";
        return "idle";
    }
    readonly property var animation: root.hasSprite ? Sprite.animation(root.spriteData, root.anim) : ({ frames: ["idle"], ms: [0], jitter: [] })
    property int frame: 0
    readonly property string spriteState: {
        const f = root.animation.frames;
        const name = f[Math.min(root.frame, f.length - 1)];
        return Sprite.hasState(root.spriteData, name) ? name : "idle";
    }

    function warmUp() {
        if (scope.visible)
            scope.warmUp();
    }

    implicitWidth: root.hasSprite ? root.size : root.scopeWidth
    implicitHeight: root.hasSprite ? root.size : root.scopeHeight

    onAnimChanged: {
        root.frame = 0;
        frameTimer.schedule();
    }

    Rectangle {
        anchors.fill: parent
        visible: root.hasSprite && root.backing
        radius: root.size / 4
        color: Theme.surface3
    }

    // Jackson in symbols (Settings.jacksonRender; "auto" = with the Phosphor theme): the same sprite and
    // the same frames drawn as characters, his eyes and mouth in the alive pink. Small sizes stay in
    // pixels: a character needs room.
    readonly property bool symbols: root.hasSprite && root.size >= 120 && (Settings.jacksonRender === "symbols" || (Settings.jacksonRender === "auto" && Theme.themeId === "phosphor"))

    PixelSprite {
        id: sprite

        anchors.centerIn: parent
        visible: root.hasSprite && !root.symbols
        pixel: root.pixelScale
        // asleep when the AI switch is off or jacksond is not running
        opacity: root.forceAnim.length === 0 && (root.mode === "off" || root.mode === "offline") ? 0.55 : 1
        grid: root.hasSprite ? Sprite.compose(root.spriteData, root.look, root.spriteState) : null
        colors: root.hasSprite ? Sprite.colors(root.spriteData, root.look, root.spriteState, Avatar.mode, Avatar.spriteAccent) : ({})
    }

    Loader {
        anchors.centerIn: parent
        active: root.symbols
        sourceComponent: AsciiView {
            width: root.size
            height: root.size
            scene: "jackson"
            mood: root.spriteState
            look: root.look
            cols: Math.max(20, Math.min(32, Math.floor(root.size / 12) * 2))
            running: false
            follow: false
            opacity: sprite.opacity
        }
    }

    // Frames of the current animation (blink: 3.6 s + up to 2.4 s, then 120 ms; talk: 140 ms).
    Timer {
        id: frameTimer

        readonly property bool active: root.hasSprite && root.visible && root.live && !Theme.reduceMotion && root.animation.frames.length > 1

        function schedule() {
            if (!frameTimer.active) {
                frameTimer.stop();
                return;
            }
            const i = Math.min(root.frame, root.animation.frames.length - 1);
            const base = root.animation.ms[i] || 140;
            const jitter = root.animation.jitter[i] || 0;
            frameTimer.interval = Math.max(60, base + Math.floor(Math.random() * jitter));
            frameTimer.restart();
        }

        onActiveChanged: {
            if (!frameTimer.active)
                root.frame = 0;
            frameTimer.schedule();
        }
        onTriggered: {
            root.frame = (root.frame + 1) % root.animation.frames.length;
            frameTimer.schedule();
        }
    }

    // keeps `now` fresh for the happy beat
    Timer {
        running: root.forceAnim.length === 0 && root.visible && Jackson.happyUntil > root.now
        interval: 200
        repeat: true
        onTriggered: root.now = Date.now()
    }

    Oscilloscope {
        id: scope

        anchors.centerIn: parent
        width: root.scopeWidth
        height: root.scopeHeight
        visible: !root.hasSprite
        mode: root.mode === "off" || root.mode === "offline" ? "idle" : root.mode
        level: Jackson.level
        live: root.live
        opacity: root.mode === "offline" || root.mode === "off" ? 0.5 : 1
    }

    // ---- right-click: «Настроить Джексона», «Глаз Джексона» (SOS ASCII over everything) --------------------
    MouseArea {
        anchors.fill: parent
        enabled: root.menu
        acceptedButtons: Qt.RightButton
        onClicked: popup.visible = !popup.visible
    }

    Rectangle {
        id: popup

        readonly property bool hovering: customizeItem.hovered || eyeItem.hovered

        visible: false
        x: 0
        y: root.height + 6
        z: 100
        width: Math.max(customizeItem.implicitWidth, eyeItem.implicitWidth) + 8
        height: menuCol.implicitHeight + 8
        radius: 8
        color: Theme.surface2
        border.width: 1
        border.color: Theme.lineStrong

        Column {
            id: menuCol

            x: 4
            y: 4

            MenuRow {
                id: customizeItem

                width: popup.width - 8
                glyph: "settings"
                text: Strings.customizeJackson
                onPicked: {
                    popup.visible = false;
                    Actions.customizeJackson();
                }
            }
            MenuRow {
                id: eyeItem

                width: popup.width - 8
                glyph: "eye"
                text: Strings.jacksonEye
                onPicked: {
                    popup.visible = false;
                    Ui.showAscii("saver");
                }
            }
        }

        onVisibleChanged: {
            if (popup.visible)
                popupHide.restart();
        }
        onHoveringChanged: {
            if (popup.hovering)
                popupHide.stop();
            else
                popupHide.restart();
        }

        Timer {
            id: popupHide

            interval: 3000
            onTriggered: popup.visible = false
        }
    }

    // (an inline component sees none of this file's ids: its width comes from the menu)
    component MenuRow: Item {
        id: item

        property string glyph: ""
        property string text: ""
        readonly property bool hovered: itemMouse.containsMouse

        signal picked

        implicitWidth: itemRow.implicitWidth + 16
        implicitHeight: 28

        Rectangle {
            anchors.fill: parent
            radius: 6
            color: item.hovered ? Theme.surface3 : "transparent"
        }

        Row {
            id: itemRow

            x: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            Icon {
                anchors.verticalCenter: parent.verticalCenter
                glyph: item.glyph
                size: 14
                color: item.hovered ? Theme.text : Theme.textDim
            }
            SText {
                anchors.verticalCenter: parent.verticalCenter
                text: item.text
                size: 13
            }
        }

        MouseArea {
            id: itemMouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: item.picked()
        }
    }
}
