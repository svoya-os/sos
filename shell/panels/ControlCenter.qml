import QtQuick
import qs.core
import qs.components

// Control center (click on the status icons, Super+A): a 380px dropdown from
// the right under the bar. Blocks: Wi-Fi · Bluetooth · Sound · Brightness ·
// Theme (Графит / Бумага / Авто + the accent → «Оформление») · Focus (Работа ·
// Обучение · Презентация) · AI & privacy (the one AI switch, route, today's spend,
// requests that left the machine) · notifications with do-not-disturb.
// «Оформление» (design/mockups/control-center-look.html, WORKFLOWS §2) is a second page:
// base theme · accent swatches with hover preview and «Свой…» · the login screen switch ·
// Jackson (mascot, «Настроить», Чёрт/Кот). Tab walks every control; Esc goes back, then closes.
PanelFrame {
    id: root

    property real maxHeight: 800
    property string passwordFor: ""   // SSID whose password row is open
    property string page: "main"      // main | look
    property var aiPending: null      // the AI switch while `sos ai on|off` runs
    property bool enablingLogin: false // the login-screen switch was just turned on

    readonly property Item pageItem: root.page === "look" ? lookPage : body

    width: 380
    height: Math.min(root.maxHeight, root.pageItem.implicitHeight)
    radius: Theme.radiusLarge
    softShadow: true

    onShownChanged: {
        Bt.watching = root.shown;
        if (root.shown) {
            root.passwordFor = "";
            root.page = Ui.ccPage === "look" ? "look" : "main";
            Ui.ccPage = "main";
            Net.refresh(true);
            Bt.refresh();
            Brightness.refresh(false);
            flick.contentY = 0;
            Qt.callLater(() => focusSink.forceActiveFocus());
        } else {
            Theme.previewAccent = "";
        }
    }

    onPageChanged: {
        flick.contentY = 0;
        Theme.previewAccent = "";
        Qt.callLater(() => focusSink.forceActiveFocus());
    }

    Item {
        id: focusSink

        focus: true
        Keys.onEscapePressed: {
            if (root.page !== "main")
                root.page = "main";
            else
                Ui.hide();
        }
    }

    // The login screen follows this user's look: `sos theme apply --system` runs once the panel
    // closes (polkit asks for the admin password; its dialog must not sit under this overlay).
    function setThemeOnLogin(on) {
        Settings.themeOnLogin = on;
        root.enablingLogin = on;
        if (on)
            Theme.queueSystemSync();
    }

    Connections {
        target: Theme

        function onSystemSyncDone(ok) {
            if (!ok) {
                if (root.enablingLogin)
                    Settings.themeOnLogin = false;
                Notifs.shellToast(Strings.onLoginFailed, "sos theme apply --system", "lock");
            }
            root.enablingLogin = false;
        }
    }

    // the one AI switch: `sos ai on|off` (Jackson and the local model servers); the switch holds the
    // new position until `sos status` reports it (or 6 s pass)
    function setAi(on) {
        root.aiPending = on;
        aiSettle.restart();
        Sys.sos(["ai", on ? "on" : "off", "--json"], function (code) {
            if (code !== 0)
                root.aiPending = null;
            Status.refresh();
        });
    }

    Timer {
        id: aiSettle

        interval: 6000
        onTriggered: root.aiPending = null
    }

    Connections {
        target: Status

        function onAiEnabledChanged() {
            if (root.aiPending === Status.aiEnabled)
                root.aiPending = null;
        }
    }

    // theme dots for the base-theme switch (fixed colors: they show the themes, not this one)
    readonly property var themeOptions: [
        { id: "graphite", label: Strings.graphite, swatch: { fill: "#141518", edge: "#4a4f57" } },
        { id: "paper", label: Strings.paper, swatch: { fill: "#f8f7f3", edge: "#bfbab0" } },
        { id: "auto", label: Strings.auto, swatch: { fill: "#141518", edge: "#8e8a81", half: "#f8f7f3" } },
        { id: "phosphor", label: Strings.phosphor, swatch: { fill: "#050806", edge: "#2b3d31", inner: "#5cf08f" } }
    ]

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
        contentHeight: root.pageItem.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: body

            width: flick.width
            visible: root.page === "main"
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
                                color: net.modelData.active ? Theme.text : Theme.textDim
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

                    TextButton {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.appearance
                        onClicked: root.page = "look"
                    }
                }

                Row {
                    width: parent.width
                    spacing: 8

                    Segmented {
                        width: parent.width - lookButton.width - 8
                        current: Theme.baseChoice
                        options: root.themeOptions.slice(0, 3)
                        onPicked: choice => Theme.setBase(choice)
                    }

                    // the accent + «›»: opens «Оформление»
                    Rectangle {
                        id: lookButton

                        width: 52
                        height: 30
                        radius: 8
                        color: lookMouse.containsMouse ? Theme.surface3 : Theme.surface
                        border.width: 1
                        border.color: Theme.line
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: Strings.appearance
                        Keys.onReturnPressed: root.page = "look"
                        Keys.onSpacePressed: root.page = "look"

                        Row {
                            anchors.centerIn: parent
                            spacing: 6

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 14
                                height: 14
                                radius: 7
                                color: Theme.accent
                                border.width: 1
                                border.color: Qt.rgba(0.5, 0.5, 0.5, 0.3)
                            }
                            Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                glyph: "chevron-right"
                                size: 13
                                stroke: 2
                                color: Theme.textDim
                            }
                        }

                        MouseArea {
                            id: lookMouse

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.page = "look"
                        }

                        FocusRing {
                            radiusBase: 8
                        }
                    }
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

                    Toggle {
                        anchors.verticalCenter: parent.verticalCenter
                        checked: root.aiPending !== null ? root.aiPending : Status.aiEnabled
                        Accessible.name: Strings.aiSwitch
                        onToggled: v => root.setAi(v)
                    }
                }

                MText {
                    text: Strings.aiSwitchSub
                    size: 11
                    color: Theme.textFaint
                    bottomPadding: 2
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

        // ==== «Оформление» ====================================================================================
        Column {
            id: lookPage

            x: 14
            width: flick.width - 28
            visible: root.page === "look"
            topPadding: 12
            spacing: 0

            // sub-page header: ‹ back · title · the command
            Item {
                width: parent.width
                height: 30

                Rectangle {
                    id: backButton

                    anchors.verticalCenter: parent.verticalCenter
                    width: 28
                    height: 28
                    radius: 8
                    color: backMouse.containsMouse ? Theme.surface3 : "transparent"
                    border.width: 1
                    border.color: Theme.lineStrong
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: Strings.back
                    Keys.onReturnPressed: root.page = "main"
                    Keys.onSpacePressed: root.page = "main"

                    Icon {
                        anchors.centerIn: parent
                        glyph: "chevron-left"
                        size: 15
                        stroke: 1.8
                        color: Theme.textDim
                    }

                    MouseArea {
                        id: backMouse

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.page = "main"
                    }

                    FocusRing {
                        radiusBase: 8
                    }
                }

                SText {
                    anchors.left: backButton.right
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.appearance
                    size: 14
                    font.weight: Font.Medium
                }

                MText {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: "sos theme"
                    size: 11
                    color: Theme.textFaint
                }
            }

            // ---- base theme ---------------------------------------------------------------------
            SectionHead {
                text: Strings.theme
                note: Strings.appliesNow
            }

            Segmented {
                width: parent.width
                current: Theme.baseChoice
                fontSize: 12
                options: root.themeOptions
                onPicked: choice => Theme.setBase(choice)
            }

            Row {
                visible: Theme.autoMode
                topPadding: 8
                leftPadding: 2
                spacing: 5

                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    glyph: Theme.isDark ? "moon" : "sun"
                    size: 12
                    stroke: 1.8
                    color: Theme.textFaint
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.autoLine
                    size: 11
                    color: Theme.textFaint
                }
            }

            // ---- accent ---------------------------------------------------------------------------
            SectionHead {
                text: Strings.accentLabel
                note: picker.shownName
            }

            AccentPicker {
                id: picker

                width: parent.width
            }

            // ---- the login screen -------------------------------------------------------------------
            Item {
                width: parent.width
                height: 16
            }

            Rectangle {
                width: parent.width
                height: 58
                radius: 12
                color: "transparent"
                border.width: 1
                border.color: Theme.line

                Column {
                    x: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 28 - loginToggle.width - 12
                    spacing: 1

                    SText {
                        width: parent.width
                        text: Strings.useOnLogin
                        size: 13
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                    MText {
                        width: parent.width
                        text: Theme.systemSyncPending ? Strings.onLoginPending : Strings.onLoginSub
                        size: 11
                        color: Theme.textFaint
                        elide: Text.ElideRight
                    }
                }

                Toggle {
                    id: loginToggle

                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    checked: Settings.themeOnLogin
                    Accessible.name: Strings.useOnLogin
                    onToggled: v => root.setThemeOnLogin(v)
                }
            }

            // ---- Jackson ----------------------------------------------------------------------------
            SectionHead {
                text: Strings.jackson
                note: Avatar.look.outfit === "accent" ? Strings.outfitLikeAccent : Strings.outfitPinned
            }

            Rectangle {
                width: parent.width
                height: jkCol.implicitHeight
                radius: 12
                color: "transparent"
                border.width: 1
                border.color: Theme.line

                Column {
                    id: jkCol

                    width: parent.width

                    Item {
                        width: parent.width
                        height: 88

                        // 64px mascot on a surface3 backing (radius 12, lineStrong edge)
                        Rectangle {
                            id: bigBox

                            x: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 64
                            height: 64
                            radius: 12
                            color: Theme.surface3
                            border.width: 1
                            border.color: Theme.lineStrong

                            JacksonAvatar {
                                anchors.centerIn: parent
                                size: 64
                                backing: false
                                live: root.shown && root.page === "look"
                                menu: false
                                scopeWidth: 52
                                scopeHeight: 16
                            }
                        }

                        Column {
                            anchors.left: bigBox.right
                            anchors.leftMargin: 14
                            anchors.right: customizeButton.left
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2

                            SText {
                                width: parent.width
                                text: Jackson.name
                                size: 14
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                            }
                            MText {
                                width: parent.width
                                text: {
                                    const look = Avatar.look;
                                    const skin = Strings.skinNames[look.skin] || look.skin;
                                    const style = Strings.cuStyles[look.style] || look.style;
                                    return (skin + " · " + style).toLowerCase();
                                }
                                size: 11
                                color: Theme.textFaint
                                elide: Text.ElideRight
                            }
                        }

                        Button {
                            id: customizeButton

                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            small: true
                            text: Strings.customize
                            onClicked: Actions.customizeJackson()
                        }
                    }

                    // Чёрт / Кот
                    Row {
                        leftPadding: 90
                        bottomPadding: 12
                        spacing: 8

                        Repeater {
                            model: [
                                { id: "imp", label: Strings.cuImp },
                                { id: "cat", label: Strings.cuCat }
                            ]

                            Rectangle {
                                id: charTile

                                required property var modelData
                                readonly property bool isCurrent: Avatar.character === modelData.id

                                width: charRow.implicitWidth + 18
                                height: 40
                                radius: 10
                                color: charTile.isCurrent ? Theme.surface3 : (charMouse.containsMouse ? Theme.surface2 : "transparent")
                                border.width: 1
                                border.color: charTile.isCurrent ? Theme.lineStrong : Theme.line
                                activeFocusOnTab: true
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: charTile.modelData.label
                                Keys.onReturnPressed: Avatar.set("character", charTile.modelData.id)
                                Keys.onSpacePressed: Avatar.set("character", charTile.modelData.id)

                                Row {
                                    id: charRow

                                    x: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 8

                                    JacksonAvatar {
                                        anchors.verticalCenter: parent.verticalCenter
                                        size: 32
                                        backing: false
                                        live: false
                                        menu: false
                                        forceAnim: "idle"
                                        scopeWidth: 28
                                        scopeHeight: 10
                                        look: Avatar.resolve(Object.assign({}, Avatar.stored, { character: charTile.modelData.id }))
                                    }
                                    SText {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: charTile.modelData.label
                                        size: 12
                                        font.weight: Font.Medium
                                        color: charTile.isCurrent ? Theme.text : Theme.textDim
                                    }
                                }

                                MouseArea {
                                    id: charMouse

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: Avatar.set("character", charTile.modelData.id)
                                }

                                FocusRing {
                                    radiusBase: 10
                                }
                            }
                        }
                    }
                }
            }

            // ---- footer: undo · all settings ---------------------------------------------------------------
            Item {
                width: parent.width
                height: 14
            }

            Rectangle {
                x: -14
                width: parent.width + 28
                height: 42
                color: "transparent"

                Divider {
                    width: parent.width
                }

                Row {
                    x: 14
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 5

                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.undoLabel
                        size: 11
                        color: Theme.textFaint
                    }
                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Super"
                    }
                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Z"
                    }
                }

                TextButton {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: Strings.allSettings + " ›"
                    onClicked: Ui.openLauncher("settings", "")
                }
            }
        }
    }

    // caps caption with a quiet note on the right (16px above, 9px below)
    component SectionHead: Item {
        id: sh

        property string text: ""
        property string note: ""

        width: parent ? parent.width : 0
        height: 16 + 11 + 9

        Caption {
            x: 2
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 9
            text: sh.text
        }

        MText {
            anchors.right: parent.right
            anchors.rightMargin: 2
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 9
            text: sh.note
            size: 11
            color: Theme.textDim
        }
    }
}
