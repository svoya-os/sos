import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.core
import qs.components

// POST screen (DESIGN.md §5): the first ~1.2 s after login. Full-screen wall
// color, Departure Mono 11/22, lines appear one by one (30 ms each) with real
// data, then a 180 ms fade to the desktop. Once per login ($XDG_RUNTIME_DIR
// marker); Settings.post = false disables it. Plays the startup sound.
Scope {
    id: root

    property bool active: false
    property bool fading: false
    property int visibleLines: 0
    property var hw: ({})

    readonly property var lines: {
        const h = root.hw;
        const g = Status.gpu;
        const r = Jackson.shownRoute;
        const out = [];
        out.push({ label: "", text: Strings.osName + " " + Sys.osVersion + "  ", morse: true });
        out.push({ label: Strings.postCpu, text: h.cpu ? h.cpu + (h.cores ? " · " + Strings.cores(h.cores) : "") : "…" });
        if (g)
            out.push({ label: Strings.postGpu, text: (g.name || "") + (g.driver ? " · " + Strings.driver + " " + g.driver : "") + (g.vramTotalMiB ? " · " + Fmt.gbFromMib(g.vramTotalMiB) + " " + Strings.gb : "") });
        else
            out.push({ label: Strings.postGpu, text: Strings.noGpu });
        out.push({ label: Strings.postRam, text: (h.ramKb ? Fmt.smart(h.ramKb / 1048576) + " " + Strings.gb : "…") + (h.diskFree ? " · " + Strings.disk + " " + Fmt.bytes(h.diskFree) + " " + Strings.free : "") });
        if (Status.aiEnabled)
            out.push({ label: Strings.postJackson + "  ", text: Jackson.connected ? ((r && r.model ? r.model + " " : "") + Strings.ready + " · " + (r && !r.local ? Strings.cloud : Strings.local)) : Strings.notRunning });
        return out;
    }

    function start() {
        if (Settings.startupSound)
            Sys.playSound("desktop-login");
        if (!Settings.post)
            return;
        root.active = true;
        gather.start();
    }

    // once per login session
    Component.onCompleted: {
        Sys.sh('m="$1/post-shown"; [ -e "$m" ] && exit 1; mkdir -p "$1" && : > "$m"', [Sys.runtimeDir], function (code) {
            if (code === 0)
                root.start();
        });
    }

    function gather() {
        Sys.sh('grep -m1 "model name" /proc/cpuinfo | cut -d: -f2-; nproc; awk \'/MemTotal/ {print $2}\' /proc/meminfo; df -B1 --output=avail / 2>/dev/null | tail -1', [], function (code, out) {
            const l = out.split("\n");
            root.hw = {
                cpu: (l[0] || "").trim().replace(/\(R\)|\(TM\)|CPU|Processor|\s+@.*$/g, "").replace(/\s+/g, " ").trim(),
                cores: Number(l[1]) || 0,
                ramKb: Number(l[2]) || 0,
                diskFree: Number(l[3]) || 0
            };
            lineTimer.start();
        });
    }

    Timer {
        id: gather

        interval: 1
        onTriggered: root.gather()
    }

    // lines appear 30 ms apart, then hold, then fade
    Timer {
        id: lineTimer

        interval: 30
        repeat: true
        onTriggered: {
            root.visibleLines += 1;
            if (root.visibleLines >= root.lines.length) {
                lineTimer.stop();
                hold.start();
            }
        }
    }

    Timer {
        id: hold

        interval: 900
        onTriggered: {
            root.fading = true;
            done.start();
        }
    }

    Timer {
        id: done

        interval: 200
        onTriggered: root.active = false
    }

    // safety: never keep the POST screen longer than 3 s
    Timer {
        running: root.active
        interval: 3000
        onTriggered: root.active = false
    }

    Variants {
        model: root.active ? Quickshell.screens : []

        PanelWindow {
            id: win

            property var modelData

            screen: win.modelData
            anchors.top: true
            anchors.bottom: true
            anchors.left: true
            anchors.right: true
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"

            WlrLayershell.namespace: "svoya-post"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

            Rectangle {
                anchors.fill: parent
                color: Theme.wall
                opacity: root.fading ? 0 : 1

                Behavior on opacity {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.OutCubic
                    }
                }

                Column {
                    x: 48
                    y: 44

                    Repeater {
                        model: root.lines

                        Row {
                            required property var modelData
                            required property int index

                            visible: index < root.visibleLines
                            height: 22

                            PixelText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.label
                                color: Theme.textDim
                            }
                            PixelText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.text
                                color: Theme.text
                            }
                            PixelText {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: modelData.morse === true
                                text: Strings.morse
                                color: Theme.textFaint
                            }
                        }
                    }
                }
            }
        }
    }
}
