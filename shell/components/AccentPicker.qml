import QtQuick
import qs.core

// Accent swatches (DESIGN §10, WORKFLOWS §2): the eight accents of themes/accents.toml in this
// theme's mode («Сигнал» split into its night and day colors), then «Свой…». Hovering a swatch
// previews it everywhere (Theme.previewAccent — nothing is written); a click applies it
// (`sos theme accent <id>`: 260 ms cross-fade, `sos undo`). «Свой…» opens a hex field with a live
// contrast badge, computed here exactly like the CLI does (WCAG against `surface`; «AA · 4,9 : 1»,
// or «поправили» when the lightness will be moved in OKLCH). The current accent carries a neutral
// `text` ring — a selection is never the accent (§11).
//
// `labels`: names under the swatches (wizard); otherwise they spread over the width (control center).
Column {
    id: root

    property bool labels: false
    property real swatch: root.labels ? 34 : 28
    property bool customOpen: false
    property string hexText: ""          // the hex field's text (the field exists only while open)

    readonly property string current: Theme.pendingAccent.length > 0 ? Theme.pendingAccent : Theme.accentChoice
    readonly property bool customCurrent: root.current.indexOf("#") === 0
    // what the hex field holds, as "#rrggbb" ("" while it is not a color yet)
    readonly property string typed: {
        const t = root.hexText.trim().toLowerCase();
        const m = /^#?([0-9a-f]{6}|[0-9a-f]{3})$/.exec(t);
        if (!m)
            return "";
        const h = m[1].length === 3 ? m[1][0] + m[1][0] + m[1][1] + m[1][1] + m[1][2] + m[1][2] : m[1];
        return "#" + h;
    }
    readonly property var typedTokens: root.typed.length > 0 ? Theme.accentTokens(root.typed) : null
    // the name of what is shown right now (hover preview first)
    readonly property string shownName: Theme.previewAccent.length > 0 ? root.nameOf(Theme.previewAccent) : root.nameOf(root.current)

    spacing: 12

    function nameOf(choice) {
        if (choice.indexOf("#") === 0)
            return Strings.customAccentName;
        const list = Theme.accentList;
        for (let i = 0; i < list.length; i++) {
            if (list[i].id === choice)
                return list[i].name;
        }
        return Theme.accentName;
    }

    function preview(choice) {
        Theme.previewAccent = choice;
    }

    function endPreview(choice) {
        if (Theme.previewAccent === choice)
            Theme.previewAccent = "";
    }

    function apply(choice) {
        Theme.previewAccent = "";
        Theme.setAccent(choice);
    }

    function toggleCustom() {
        if (root.customOpen) {
            root.endPreview(root.typed);
            root.customOpen = false;
            return;
        }
        root.hexText = root.customCurrent ? root.current.slice(1) : "";
        root.customOpen = true;
    }

    function hexEdited(text) {
        root.hexText = text;
        if (root.typed.length > 0)
            root.preview(root.typed);
        else if (Theme.previewAccent.indexOf("#") === 0)
            root.preview("");
    }

    function hexAccepted() {
        if (root.typed.length === 0)
            return;
        root.apply(root.typed);
        root.customOpen = false;
    }

    function hexCancelled() {
        root.endPreview(root.typed);
        root.customOpen = false;
    }

    // a preview never outlives the picker (panel closed while hovering)
    onVisibleChanged: {
        if (!root.visible) {
            Theme.previewAccent = "";
            root.customOpen = false;
        }
    }
    Component.onDestruction: Theme.previewAccent = ""

    // ---- swatches -----------------------------------------------------------------------------------
    Item {
        id: strip

        readonly property int count: Theme.accentList.length + 1
        readonly property real cell: root.swatch + 8
        readonly property real gap: root.labels ? 16 : Math.max(0, (strip.width - strip.count * strip.cell) / Math.max(1, strip.count - 1))

        width: parent.width
        height: strip.cell + (root.labels ? 20 : 0)

        Row {
            spacing: strip.gap

            Repeater {
                model: Theme.accentList

                Column {
                    id: cellItem

                    required property var modelData
                    readonly property bool isCurrent: root.current === modelData.id
                    readonly property var accent: Theme.accentById(modelData.id)

                    width: strip.cell
                    spacing: 4

                    Swatch {
                        anchors.horizontalCenter: parent.horizontalCenter
                        size: root.swatch
                        color: cellItem.modelData.id === "signal" && cellItem.accent ? cellItem.accent.dark : cellItem.modelData.color
                        second: cellItem.accent ? cellItem.accent.light : cellItem.modelData.color
                        split: cellItem.modelData.id === "signal"
                        selected: cellItem.isCurrent
                        label: cellItem.modelData.name
                        onHoveredChanged: hovered ? root.preview(cellItem.modelData.id) : root.endPreview(cellItem.modelData.id)
                        onPicked: root.apply(cellItem.modelData.id)
                    }

                    MText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: root.labels
                        text: cellItem.modelData.name
                        size: 11
                        color: cellItem.isCurrent ? Theme.text : Theme.textDim
                    }
                }
            }

            Column {
                width: strip.cell
                spacing: 4

                Swatch {
                    anchors.horizontalCenter: parent.horizontalCenter
                    size: root.swatch
                    rainbow: true
                    empty: !root.customCurrent && !(root.customOpen && root.typed.length > 0)
                    color: root.customOpen && root.typed.length > 0 ? root.typed : (root.customCurrent ? root.current : Theme.surface2)
                    selected: root.customCurrent || root.customOpen
                    label: Strings.customAccent
                    onPicked: root.toggleCustom()
                }

                MText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.labels
                    text: Strings.customAccent
                    size: 11
                    color: root.customCurrent ? Theme.text : Theme.textDim
                }
            }
        }
    }

    // ---- «Свой…»: hex field + contrast badge (created only while open: a hidden field must never
    // hold the keyboard focus of the panel or the wizard step) -----------------------------------------
    Loader {
        width: parent.width
        active: root.customOpen
        visible: root.customOpen
        sourceComponent: hexComponent
    }

    Component {
        id: hexComponent

        Rectangle {
            id: hexBox

            width: parent ? parent.width : 0
            height: 36
            radius: Theme.radiusButton
            color: Theme.surface
            border.width: 1
            border.color: hexField.input.activeFocus ? Theme.text : Theme.lineStrong

            Component.onCompleted: {
                hexField.text = root.hexText;
                hexField.focusInput();
            }

            // 3px `line` halo while focused (DESIGN §9 text fields)
            Rectangle {
                anchors.fill: parent
                anchors.margins: -3
                z: -1
                radius: parent.radius + 3
                visible: hexField.input.activeFocus
                color: "transparent"
                border.width: 3
                border.color: Theme.line
            }

            Rectangle {
                id: chip

                x: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 14
                radius: 4
                color: root.typed.length > 0 ? root.typed : Theme.surface3
                border.width: 1
                border.color: Qt.rgba(0.5, 0.5, 0.5, 0.3)
            }

            MText {
                id: hash

                anchors.left: chip.right
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: "#"
                size: 13
                color: Theme.textFaint
            }

            TextField {
                id: hexField

                anchors.left: hash.right
                anchors.leftMargin: 1
                anchors.right: badge.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                size: 13
                mono: true
                placeholder: "7b61ff"
                onTextChanged: root.hexEdited(hexField.text)
                onAccepted: root.hexAccepted()
                onEscape: root.hexCancelled()
            }

            // live contrast badge: ok tag «✓ AA · 4,9 : 1» or a line tag «поправили · 4,6 : 1»
            Rectangle {
                id: badge

                readonly property bool ok: root.typedTokens !== null && !root.typedTokens.adjusted

                anchors.right: parent.right
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                visible: root.typedTokens !== null
                width: visible ? badgeRow.implicitWidth + 16 : 0
                height: 24
                radius: 7
                color: badge.ok ? Theme.alpha(Theme.ok, 0.12) : "transparent"
                border.width: badge.ok ? 0 : 1
                border.color: Theme.lineStrong

                Row {
                    id: badgeRow

                    anchors.centerIn: parent
                    spacing: 5

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: badge.ok
                        glyph: "check"
                        size: 12
                        stroke: 2.4
                        color: Theme.ok
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.typedTokens === null ? "" : (badge.ok ? Strings.contrastOk(root.typedTokens.contrast) : Strings.contrastFixed(root.typedTokens.contrast))
                        size: 11
                        color: badge.ok ? Theme.ok : Theme.textDim
                    }
                }
            }
        }
    }

    // what the badge means, in words
    Row {
        visible: root.customOpen
        width: parent.width
        spacing: 6

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.typedTokens !== null && root.typedTokens.adjusted
            width: 9
            height: 9
            radius: 3
            color: root.typedTokens ? root.typedTokens.color : "transparent"
        }
        MText {
            width: parent.width - 20
            wrapMode: Text.WordWrap
            text: {
                const t = root.typedTokens;
                if (root.hexText.trim().length === 0)
                    return Strings.hexHint;
                if (t === null)
                    return Strings.contrastBadHex;
                return t.adjusted ? Strings.hexNoteAdjusted(Theme.isDark, t.color) : Strings.hexNoteOk(Theme.isDark);
            }
            size: 11
            lineHeight: 1.35
            color: Theme.textFaint
        }
    }
}
