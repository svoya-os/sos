import QtQuick
import qs.core
import qs.components

// Control center (click on the status icons, Super+A): a 380px dropdown from
// the right under the bar. Blocks: Wi-Fi · Bluetooth · Sound · Brightness ·
// Theme (Графит / Бумага / Авто) · Focus (Работа · Обучение · Презентация) ·
// AI & privacy (route, today's spend, requests that left the machine) ·
// notifications with do-not-disturb. Tab walks every control; Esc closes.
PanelFrame {
    id: root

    property real maxHeight: 800
    property string passwordFor: ""   // SSID whose password row is open

    width: 380
    height: Math.min(root.maxHeight, body.implicitHeight)
    radius: Theme.radiusLarge
    softShadow: true

    onShownChanged: {
        Bt.watching = root.shown;
        if (root.shown) {
            root.passwordFor = "";
            Net.refresh(true);
            Bt.refresh();
            Brightness.refresh(false);
            flick.contentY = 0;
            Qt.callLater(() => focusSink.forceActiveFocus());
        }
    }

    Item {
        id: focusSink

        focus: true
        Keys.onEscapePressed: Ui.hide()
    }

    component BlockTitle: Item {
        id: bt

        property string text: ""
        default property alias trailing: slot.data

        width: parent ? parent.width : 0
        height: 28

        Caption {
            anchors.verticalCenter: parent.verticalCenter
            text: bt.text
        }

        Row {
            id: slot

            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
        }
    }

    Flickable {
        id: flick

        anchors.fill: parent
        contentHeight: body.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: body

            width: flick.width
            topPadding: 14
            bottomPadding: 14
            spacing: 0

            // ---- network ---------------------------------------------------------------------
            Column {
                x: 16
                width: parent.width - 32
                spacing: 4
                visible: Net.available

                BlockTitle {
                    text: Strings.network

                    Toggle {
                        visible: Net.hasWifiDevice
                        checked: Net.wifiEnabled
                        onToggled: v => Net.setWifi(v)
                    }
                }

                MText {
                    text: Net.kind === "wifi" ? Net.ssid + " · " + Strings.connected : (Net.kind === "ethernet" ? Strings.wired + " · " + Strings.connected : (Net.wifiEnabled || !Net.hasWifiDevice ? Strings.offline : Strings.wifiOff))
                    size: 11
                    color: Theme.textDim
                    bottomPadding: 4
                }

                Repeater {
                    model: Net.wifiEnabled ? Net.networks.slice(0, 6) : []

                    Column {
                        id: net

                        required property var modelData

                        width: parent.width

                        Rectangle {
                            width: parent.width
                            height: 32
                            radius: 8
                            color: netMouse.containsMouse || netRow.activeFocus ? Theme.surface3 : "transparent"

                            Item {
                                id: netRow

                                anchors.fill: parent
                                activeFocusOnTab: true
                                Keys.onReturnPressed: net.activate()
                                Keys.onSpacePressed: net.activate()

                                FocusRing {
                                    radiusBase: 8
                                }
                            }

                            Icon {
                                x: 8
                                anchors.verticalCenter: parent.verticalCenter
                                glyph: net.modelData.signal >= 60 ? "svoya-wifi" : (net.modelData.signal >= 35 ? "wifi-high" : "wifi-low")
                                color: net.modelData.active ? Theme.accent : Theme.textDim
                            }

                            SText {
                                x: 34
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 34 - trail.width - 16
                                text: net.modelData.ssid
                                size: 13
                                elide: Text.ElideRight
                                color: Theme.text
                            }

                            Row {
                                id: trail

                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8

                                MText {
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: net.modelData.active || Net.busySsid === net.modelData.ssid
                                    text: Net.busySsid === net.modelData.ssid ? Strings.connecting : Strings.connected
                                    size: 11
                                    color: Theme.textFaint
                                }
                                Icon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: net.modelData.secure
                                    glyph: "lock"
                                    size: 13
                                    color: Theme.textFaint
                                }
                            }

                            MouseArea {
                                id: netMouse

                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: net.activate()
                            }
                        }

                        function activate() {
                            const n = net.modelData;
                            if (n.active)
                                Net.disconnectFrom(n.ssid);
                            else if (n.secure && !n.known)
                                root.passwordFor = root.passwordFor === n.ssid ? "" : n.ssid;
                            else
                                Net.connectTo(n.ssid, "");
                        }

                        // inline password
                        Rectangle {
                            visible: root.passwordFor === net.modelData.ssid
                            width: parent.width
                            height: visible ? 38 : 0
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.lineStrong

                            TextField {
                                id: pw

                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                password: true
                                placeholder: Strings.password
                                onAccepted: {
                                    Net.connectTo(net.modelData.ssid, pw.text);
                                    pw.text = "";
                                    root.passwordFor = "";
                                }
                                onEscape: root.passwordFor = ""
                                onVisibleChanged: if (visible) Qt.callLater(pw.focusInput)
                            }
                        }
                    }
                }

                MText {
                    visible: Net.lastError.length > 0
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: Net.lastError
                    size: 11
                    color: Theme.bad
                }
            }

            Divider {
                width: parent.width
                visible: Net.available
                opacity: 0.8
            }

            // ---- bluetooth -----------------------------------------------------------------------
            Item {
                width: parent.width
                height: 50
                visible: Bt.tool && Bt.controller

                Column {
                    x: 16
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2

                    Caption {
                        text: Strings.bluetooth
                    }
                    MText {
                        text: Bt.powered ? (Bt.connectedNames.length > 0 ? Bt.connectedNames.join(", ") : Strings.btOn) : Strings.btOff
                        size: 11
                        color: Theme.textDim
                    }
                }

                Toggle {
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    checked: Bt.powered
                    onToggled: v => Bt.setPowered(v)
                }
            }

            Divider {
                width: parent.width
                visible: Bt.tool && Bt.controller
                opacity: 0.8
            }

            // ---- sound & brightness --------------------------------------------------------------------
            Column {
                x: 16
                width: parent.width - 32
                topPadding: 10
                bottomPadding: 10
                spacing: 10

                Row {
                    width: parent.width
                    spacing: 12
                    visible: Audio.ready

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        glyph: Audio.icon
                        size: 16

                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -6
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Audio.toggleMute()
                        }
                    }

                    Slider {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 16 - 12 - 12 - 40
                        value: Audio.muted ? 0 : Audio.volume
                        onMoved: v => Audio.setVolume(v)
                    }

                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 40
                        horizontalAlignment: Text.AlignRight
                        text: Audio.muted ? Strings.muted : Fmt.pct(Audio.volume)
                        size: 11
                    }
                }

                Row {
                    width: parent.width
                    spacing: 12
                    visible: Brightness.available

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        glyph: "sun"
                        size: 16
                    }

                    Slider {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 16 - 12 - 12 - 40
                        value: Brightness.value
                        onMoved: v => Brightness.set(v)
                    }

                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 40
                        horizontalAlignment: Text.AlignRight
                        text: Fmt.pct(Brightness.value)
                        size: 11
                    }
                }
            }

            Divider {
                width: parent.width
                opacity: 0.8
            }

            // ---- theme & focus ----------------------------------------------------------------------
            Column {
                x: 16
                width: parent.width - 32
                topPadding: 10
                bottomPadding: 12
                spacing: 8

                BlockTitle {
                    text: Strings.theme
                }

                Segmented {
                    width: parent.width
                    current: Theme.autoMode ? "auto" : Theme.themeId
                    options: [
                        { id: "graphite", label: Strings.graphite },
                        { id: "paper", label: Strings.paper },
                        { id: "auto", label: Strings.auto }
                    ]
                    onPicked: choice => Sys.sos(["theme", "apply", choice, "--quiet"])
                }

                BlockTitle {
                    text: Strings.focus
                }

                Segmented {
                    width: parent.width
                    current: Settings.focusMode
                    options: [
                        { id: "work", label: Strings.focusWork },
                        { id: "study", label: Strings.focusStudy },
                        { id: "presentation", label: Strings.focusPresentation }
                    ]
                    onPicked: choice => Settings.focusMode = Settings.focusMode === choice ? "" : choice
                }
            }

            Divider {
                width: parent.width
                opacity: 0.8
            }

            // ---- AI & privacy ---------------------------------------------------------------------------
            Column {
                x: 16
                width: parent.width - 32
                topPadding: 10
                bottomPadding: 12
                spacing: 6

                BlockTitle {
                    text: Strings.aiPrivacy
                }

                Row {
                    spacing: 8
                    visible: Status.aiEnabled

                    Dot {
                        anchors.verticalCenter: parent.verticalCenter
                        color: Status.cloudActive || (Jackson.shownRoute && !Jackson.shownRoute.local) ? Theme.cloud : Theme.ok
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        size: 11.5
                        color: Theme.text
                        text: {
                            const r = Jackson.shownRoute;
                            if (!Jackson.connected)
                                return Jackson.name + " · " + Strings.jacksonOffline;
                            if (r && !r.local)
                                return Strings.cloud + " · " + (r.provider || r.model);
                            return Strings.local + (r && r.model ? " · " + r.model : "");
                        }
                    }
                }

                MText {
                    visible: !Status.aiEnabled
                    text: Strings.jacksonDisabled
                    size: 11.5
                    color: Theme.textDim
                }

                Row {
                    spacing: 8

                    MText {
                        text: Strings.spentToday
                        size: 11
                        color: Theme.textFaint
                    }
                    MText {
                        text: Strings.euro(Status.costToday)
                        size: 11
                        color: Theme.textDim
                    }
                }

                Row {
                    spacing: 8

                    MText {
                        text: Strings.leftToday
                        size: 11
                        color: Theme.textFaint
                    }
                    MText {
                        text: Status.cloudRequestsToday > 0 ? Strings.requests(Status.cloudRequestsToday) : Strings.aiLocalOnly
                        size: 11
                        color: Status.cloudRequestsToday > 0 ? Theme.cloud : Theme.ok
                    }
                }
            }

            Divider {
                width: parent.width
                opacity: 0.8
            }

            // ---- notifications ------------------------------------------------------------------------------
            Column {
                x: 16
                width: parent.width - 32
                topPadding: 10
                spacing: 6

                BlockTitle {
                    text: Strings.notifications

                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.dnd
                        size: 11
                        color: Theme.textFaint
                    }
                    Toggle {
                        anchors.verticalCenter: parent.verticalCenter
                        checked: Settings.dnd
                        onToggled: v => Settings.dnd = v
                    }
                    Button {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: Notifs.count > 0
                        small: true
                        text: Strings.clearAll
                        onClicked: Notifs.clearAll()
                    }
                }

                MText {
                    visible: Notifs.count === 0
                    text: Strings.noNotifications
                    size: 11
                    color: Theme.textFaint
                    bottomPadding: 4
                }

                Repeater {
                    model: Notifs.history.slice(0, 30)

                    NotificationCard {
                        required property var modelData

                        width: parent.width
                        notification: modelData
                        compact: true
                    }
                }
            }
        }
    }
}
