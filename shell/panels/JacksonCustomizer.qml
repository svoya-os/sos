import QtQuick
import qs.core
import qs.components

// «Настроить Джексона» (DESIGN §13, design/mockups/jackson-customize.html): right-click the
// mascot, the control center («Оформление» → «Настроить»), IPC `jackson customize`.
//
// Left: a 192 px preview that walks through his states (idle · listening · thinking · talking ·
// happy · error; click a thumbnail to hold one, pause to stop), and how he looks in the panel.
// Right: character, skin/fur, outfit («как акцент» or a pinned accent color), style, glasses,
// hood, headphones; then his name, humor and persona.
//
// Every change is written at once: the look to ~/.config/svoya/avatar.json (Avatar: atomic, keys
// this shell does not know are kept; jacksond watches the same file), persona and humor through
// Jackson's own CLI (`j persona set …`, `j persona humor …`). «Вернуть как было» restores what was
// there when the panel opened; «По умолчанию» is `j avatar reset`. Esc or «Готово» closes.
PanelFrame {
    id: root

    readonly property var stateList: ["idle", "listening", "thinking", "talking", "happy", "error"]
    property string pinned: ""          // a state held by clicking its thumbnail ("" = walk through)
    property bool paused: false
    property int cycleIndex: 0
    readonly property string previewAnim: root.pinned.length > 0 ? root.pinned : root.stateList[root.cycleIndex]

    // what was there when the panel opened («вернуть как было»)
    property string snapshot: "{}"
    property string snapshotPersona: ""
    property int snapshotHumor: 1
    readonly property bool changed: JSON.stringify(Avatar.stored) !== root.snapshot || Jackson.personaId !== root.snapshotPersona || Jackson.humor !== root.snapshotHumor

    readonly property var look: Avatar.look
    readonly property string character: root.look.character
    readonly property bool nameOk: Avatar.validName(nameField.text)

    readonly property real leftWidth: 316
    readonly property real rightWidth: root.width - 48 - root.leftWidth - 28

    width: 920
    implicitHeight: col.implicitHeight

    onShownChanged: {
        if (!root.shown) {
            root.commitName();
            return;
        }
        root.snapshot = JSON.stringify(Avatar.stored);
        root.snapshotPersona = Jackson.personaId;
        root.snapshotHumor = Jackson.humor;
        root.pinned = "";
        root.paused = false;
        root.cycleIndex = 0;
        nameField.text = Avatar.name;
        preview.warmUp();
        Qt.callLater(() => focusSink.forceActiveFocus());
    }

    function set(key, value) {
        Avatar.set(key, value);
    }

    function commitName() {
        nameCommit.stop();
        const n = nameField.text.trim();
        if (n.length > 0 && Avatar.validName(n) && n !== Avatar.name)
            Avatar.set("name", n);
    }

    function revert() {
        try {
            Avatar.write(JSON.parse(root.snapshot));
        } catch (e) {
            Avatar.write({});
        }
        if (Jackson.personaId !== root.snapshotPersona && root.snapshotPersona.length > 0)
            Jackson.setPersona(root.snapshotPersona);
        if (Jackson.humor !== root.snapshotHumor)
            Jackson.setHumor(root.snapshotHumor);
        nameField.text = Avatar.name;
    }

    function resetLook() {
        Avatar.reset();
        nameField.text = Avatar.name;
    }

    Item {
        id: focusSink

        focus: true
        Keys.onEscapePressed: Ui.hide()
        Keys.onReturnPressed: Ui.hide()
    }

    // the preview walks through the states every 2.4 s
    Timer {
        running: root.shown && !root.paused && root.pinned.length === 0 && !Theme.reduceMotion
        interval: 2400
        repeat: true
        onTriggered: root.cycleIndex = (root.cycleIndex + 1) % root.stateList.length
    }

    Timer {
        id: nameCommit

        interval: 700
        onTriggered: root.commitName()
    }

    // a row of the right column: label on the left, the control after 120 px, a hairline below
    component Field: Item {
        id: field

        property string label: ""
        property bool last: false
        default property alias control: slot.data

        width: parent ? parent.width : 0
        height: Math.max(44, slot.childrenRect.height + 14)

        SText {
            anchors.verticalCenter: parent.verticalCenter
            text: field.label
            size: 13
            color: Theme.textDim
        }

        Item {
            id: slot

            x: 112
            width: parent.width - 112
            height: slot.childrenRect.height
            anchors.verticalCenter: parent.verticalCenter
        }

        Divider {
            anchors.bottom: parent.bottom
            width: parent.width
            visible: !field.last
        }
    }

    Column {
        id: col

        width: parent.width

        // ---- head ------------------------------------------------------------------------------------
        Item {
            width: parent.width
            height: 78

            Column {
                x: 24
                y: 20
                width: parent.width - 48 - hints.width - 24
                spacing: 6

                SText {
                    text: Jackson.name
                    size: Theme.fsTitle
                    font.weight: Font.Medium
                }
                SText {
                    width: parent.width
                    text: Strings.cuSub
                    size: 13
                    color: Theme.textDim
                    elide: Text.ElideRight
                }
            }

            Column {
                id: hints

                anchors.right: parent.right
                anchors.rightMargin: 24
                y: 26
                spacing: 4

                MText {
                    anchors.right: parent.right
                    text: Strings.cuCmd
                    size: 11
                    color: Theme.textDim
                }
                MText {
                    anchors.right: parent.right
                    text: Strings.cuSay
                    size: 11
                    color: Theme.textFaint
                }
            }
        }

        Row {
            x: 24
            spacing: 28

            // ==== left: preview ==========================================================================
            Column {
                width: root.leftWidth
                spacing: 12

                Rectangle {
                    width: parent.width
                    height: 292
                    radius: 12
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.line

                    Caption {
                        x: 16
                        y: 14
                        text: Strings.cuPreview
                    }

                    JacksonAvatar {
                        id: preview

                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 38
                        size: 192
                        backing: false
                        menu: false
                        forceAnim: root.previewAnim
                        live: root.shown && !root.paused
                        scopeWidth: 180
                        scopeHeight: 60
                    }

                    MText {
                        x: 16
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 16
                        text: (Strings.cuStates[root.previewAnim] || root.previewAnim) + " · " + Strings.cuFrames(preview.animation.frames.length, preview.animation.ms[0] || 0)
                        size: 11
                        color: Theme.textFaint
                    }

                    // pause / walk through the states
                    Rectangle {
                        id: pauseButton

                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 10
                        width: 28
                        height: 28
                        radius: 8
                        color: pauseMouse.containsMouse ? Theme.surface3 : "transparent"
                        border.width: 1
                        border.color: Theme.lineStrong
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: root.paused || root.pinned.length > 0 ? Strings.cuPlay : Strings.cuPause
                        Keys.onReturnPressed: pauseMouse.flip()
                        Keys.onSpacePressed: pauseMouse.flip()

                        Row {
                            anchors.centerIn: parent
                            visible: !root.paused && root.pinned.length === 0
                            spacing: 3

                            Rectangle {
                                width: 3
                                height: 10
                                radius: 1
                                color: Theme.textDim
                            }
                            Rectangle {
                                width: 3
                                height: 10
                                radius: 1
                                color: Theme.textDim
                            }
                        }

                        Icon {
                            anchors.centerIn: parent
                            visible: root.paused || root.pinned.length > 0
                            glyph: "svoya-play"
                            size: 13
                            color: Theme.textDim
                        }

                        MouseArea {
                            id: pauseMouse

                            function flip() {
                                if (root.pinned.length > 0) {
                                    root.pinned = "";
                                    root.paused = false;
                                } else {
                                    root.paused = !root.paused;
                                }
                            }

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: pauseMouse.flip()
                        }

                        FocusRing {
                            radiusBase: 8
                        }
                    }
                }

                // thumbnails: click to hold a state
                Row {
                    spacing: (parent.width - 6 * 42) / 5

                    Repeater {
                        model: root.stateList

                        Column {
                            id: thumb

                            required property string modelData
                            readonly property bool isShown: root.previewAnim === modelData

                            width: 42
                            spacing: 4

                            Rectangle {
                                width: 42
                                height: 42
                                radius: 10
                                color: Theme.surface3
                                border.width: thumb.isShown ? 2 : 1
                                border.color: thumb.isShown ? Theme.selected : Theme.line
                                activeFocusOnTab: true
                                Accessible.role: Accessible.Button
                                Accessible.name: Strings.cuStates[thumb.modelData] || thumb.modelData
                                Keys.onReturnPressed: root.pinned = root.pinned === thumb.modelData ? "" : thumb.modelData
                                Keys.onSpacePressed: root.pinned = root.pinned === thumb.modelData ? "" : thumb.modelData

                                JacksonAvatar {
                                    anchors.centerIn: parent
                                    size: 32
                                    backing: false
                                    menu: false
                                    live: false
                                    forceAnim: thumb.modelData
                                    scopeWidth: 36
                                    scopeHeight: 12
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.pinned = root.pinned === thumb.modelData ? "" : thumb.modelData
                                }

                                FocusRing {
                                    radiusBase: 10
                                }
                            }

                            // a label wider than the tile overflows evenly without moving the row
                            MText {
                                width: 42
                                horizontalAlignment: Text.AlignHCenter
                                text: Strings.cuStates[thumb.modelData] || thumb.modelData
                                size: 10.5
                                color: thumb.isShown ? Theme.text : Theme.textFaint
                            }
                        }
                    }
                }

                // how he looks in the panel head
                Caption {
                    topPadding: 6
                    text: Strings.cuInPanel
                }

                Rectangle {
                    width: parent.width
                    height: 52
                    radius: 12
                    color: Theme.surface2
                    border.width: 1
                    border.color: Theme.lineStrong

                    Row {
                        x: 10
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10

                        JacksonAvatar {
                            anchors.verticalCenter: parent.verticalCenter
                            size: 32
                            menu: false
                            live: root.shown
                            scopeWidth: 40
                            scopeHeight: 14
                        }
                        SText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Jackson.name
                            size: 13
                            font.weight: Font.Medium
                        }
                        Chip {
                            anchors.verticalCenter: parent.verticalCenter
                            dotColor: Jackson.shownRoute && !Jackson.shownRoute.local ? Theme.cloud : Theme.ok
                            text: Jackson.shownRoute && !Jackson.shownRoute.local ? Strings.cloud : Strings.local
                        }
                    }
                }
            }

            // ==== right: the look, then the character ======================================================
            Column {
                width: root.rightWidth

                Field {
                    label: Strings.cuCharacter

                    Row {
                        spacing: 8

                        Repeater {
                            model: Avatar.characters

                            Rectangle {
                                id: charTile

                                required property string modelData
                                readonly property bool isCurrent: root.character === modelData

                                width: charRow.implicitWidth + 20
                                height: 44
                                radius: 10
                                color: charTile.isCurrent ? Theme.surface3 : (charMouse.containsMouse ? Theme.surface2 : "transparent")
                                border.width: 1
                                border.color: charTile.isCurrent ? Theme.lineStrong : Theme.line
                                activeFocusOnTab: true
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: charTile.modelData === "cat" ? Strings.cuCat : Strings.cuImp
                                Keys.onReturnPressed: root.set("character", charTile.modelData)
                                Keys.onSpacePressed: root.set("character", charTile.modelData)

                                Row {
                                    id: charRow

                                    x: 6
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 8

                                    JacksonAvatar {
                                        anchors.verticalCenter: parent.verticalCenter
                                        size: 32
                                        backing: false
                                        menu: false
                                        live: false
                                        forceAnim: "idle"
                                        look: Avatar.resolve(Object.assign({}, Avatar.stored, { character: charTile.modelData }))
                                        scopeWidth: 28
                                        scopeHeight: 10
                                    }
                                    SText {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: charTile.modelData === "cat" ? Strings.cuCat : Strings.cuImp
                                        size: 13
                                        font.weight: Font.Medium
                                        color: charTile.isCurrent ? Theme.text : Theme.textDim
                                    }
                                    MText {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: Strings.cuCharacterSubs[charTile.modelData] || ""
                                        size: 11
                                        color: Theme.textFaint
                                    }
                                }

                                MouseArea {
                                    id: charMouse

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.set("character", charTile.modelData)
                                }

                                FocusRing {
                                    radiusBase: 10
                                }
                            }
                        }
                    }
                }

                Field {
                    label: root.character === "cat" ? Strings.cuFur : Strings.cuSkin

                    Row {
                        spacing: 6

                        Repeater {
                            model: Avatar.skins[root.character]

                            Column {
                                id: skinCell

                                required property string modelData

                                width: 58
                                spacing: 2

                                Swatch {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    size: 26
                                    color: Avatar.skinColor(skinCell.modelData, root.character)
                                    selected: root.look.skin === skinCell.modelData
                                    label: Avatar.skinName(skinCell.modelData, root.character)
                                    onPicked: root.set("skin", skinCell.modelData)
                                }
                                MText {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    elide: Text.ElideRight
                                    text: Avatar.skinName(skinCell.modelData, root.character)
                                    size: 10.5
                                    color: root.look.skin === skinCell.modelData ? Theme.text : Theme.textFaint
                                }
                            }
                        }
                    }
                }

                Field {
                    label: Strings.cuOutfit

                    Row {
                        spacing: 6

                        // «как акцент»: follows the system accent
                        Rectangle {
                            id: likeAccent

                            readonly property bool isCurrent: root.look.outfit === "accent"

                            anchors.verticalCenter: parent.verticalCenter
                            width: likeRow.implicitWidth + 22
                            height: 30
                            radius: 15
                            color: likeMouse.containsMouse && !likeAccent.isCurrent ? Theme.surface2 : "transparent"
                            border.width: likeAccent.isCurrent ? 1.5 : 1
                            border.color: likeAccent.isCurrent ? Theme.selected : Theme.line
                            activeFocusOnTab: true
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: Strings.cuAsAccent
                            Keys.onReturnPressed: root.set("outfit", "accent")
                            Keys.onSpacePressed: root.set("outfit", "accent")

                            Row {
                                id: likeRow

                                anchors.centerIn: parent
                                spacing: 7

                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 14
                                    height: 14
                                    radius: 7
                                    color: Avatar.outfitColor("accent", root.character)
                                    border.width: 1
                                    border.color: Qt.rgba(0.5, 0.5, 0.5, 0.3)
                                }
                                SText {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Strings.cuAsAccent
                                    size: 12.5
                                    font.weight: likeAccent.isCurrent ? Font.Medium : Font.Normal
                                    color: likeAccent.isCurrent ? Theme.text : Theme.textDim
                                }
                            }

                            MouseArea {
                                id: likeMouse

                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.set("outfit", "accent")
                            }

                            FocusRing {
                                radiusBase: 15
                            }
                        }

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 1
                            height: 20
                            color: Theme.line
                        }

                        // or one accent's outfit color, pinned
                        Repeater {
                            model: Theme.accentList

                            Swatch {
                                required property var modelData

                                anchors.verticalCenter: parent.verticalCenter
                                size: 18
                                color: Avatar.outfitColor(modelData.id, root.character)
                                selected: root.look.outfit === modelData.id
                                label: modelData.name
                                onPicked: root.set("outfit", modelData.id)
                            }
                        }
                    }
                }

                Field {
                    label: Strings.cuStyle

                    Segmented {
                        width: parent.width
                        current: root.look.style
                        options: Avatar.styles.map(k => ({ "id": k, "label": Strings.cuStyles[k] || k }))
                        onPicked: key => root.set("style", key)
                    }
                }

                Field {
                    label: Strings.cuGlasses

                    Segmented {
                        width: parent.width
                        current: root.look.glasses
                        options: Avatar.glassesKinds.map(k => ({ "id": k, "label": Strings.cuGlassesKinds[k] || k }))
                        onPicked: key => root.set("glasses", key)
                    }
                }

                Field {
                    label: Strings.cuDetails

                    Row {
                        spacing: 22

                        Row {
                            visible: root.character === "imp"
                            spacing: 10

                            Toggle {
                                anchors.verticalCenter: parent.verticalCenter
                                checked: root.look.hood
                                Accessible.name: Strings.cuHood
                                onToggled: v => root.set("hood", v)
                            }
                            SText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.cuHood
                                size: 13
                            }
                        }

                        Row {
                            spacing: 10

                            Toggle {
                                anchors.verticalCenter: parent.verticalCenter
                                checked: root.look.headphones
                                Accessible.name: Strings.cuHeadphones
                                onToggled: v => root.set("headphones", v)
                            }
                            SText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Strings.cuHeadphones
                                size: 13
                            }
                        }
                    }
                }

                // ---- character: name, humor, persona -----------------------------------------------------
                Item {
                    width: parent.width
                    height: 34

                    Caption {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 8
                        text: Strings.cuCharacterSection
                    }
                    MText {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 8
                        text: Strings.cuCharacterNote
                        size: 11
                        color: Theme.textFaint
                    }
                }

                Field {
                    label: Strings.cuName

                    Row {
                        spacing: 12

                        Rectangle {
                            id: nameBox

                            width: 220
                            height: 34
                            radius: Theme.radiusButton
                            color: Theme.surface
                            border.width: 1
                            border.color: nameField.input.activeFocus ? Theme.text : Theme.lineStrong

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -3
                                z: -1
                                radius: parent.radius + 3
                                visible: nameField.input.activeFocus
                                color: "transparent"
                                border.width: 3
                                border.color: Theme.line
                            }

                            TextField {
                                id: nameField

                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                size: 13.5
                                placeholder: Avatar.defaultName
                                onTextChanged: {
                                    if (nameField.input.activeFocus)
                                        nameCommit.restart();
                                }
                                onAccepted: root.commitName()
                                onEscapePressed: Ui.hide()
                            }
                        }

                        MText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.nameOk || nameField.text.length === 0 ? Strings.cuNameHint : Strings.cuNameBad
                            size: 11
                            color: root.nameOk || nameField.text.length === 0 ? Theme.textFaint : Theme.warn
                        }
                    }
                }

                Field {
                    label: Strings.cuHumor

                    Row {
                        spacing: 12

                        MText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Strings.cuHumorLow
                            size: 11
                            color: Theme.textFaint
                        }
                        Slider {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 160
                            value: Jackson.humor / 2
                            Accessible.name: Strings.cuHumor
                            onMoved: v => {
                                const level = Math.round(v * 2);
                                if (level !== Jackson.humor)
                                    Jackson.setHumor(level);
                            }
                        }
                        MText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Strings.cuHumorHigh
                            size: 11
                            color: Theme.textFaint
                        }
                    }
                }

                Field {
                    label: Strings.cuPersona
                    last: true

                    Grid {
                        columns: 2
                        spacing: 8

                        Repeater {
                            model: Jackson.personas

                            Rectangle {
                                id: card

                                required property string modelData
                                readonly property bool isCurrent: Jackson.personaId === modelData

                                width: (root.rightWidth - 112 - 8) / 2
                                height: 50
                                radius: 10
                                color: cardMouse.containsMouse && !card.isCurrent ? Theme.surface2 : "transparent"
                                border.width: card.isCurrent ? 1.5 : 1
                                border.color: card.isCurrent ? Theme.selected : Theme.line
                                activeFocusOnTab: true
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: Strings.cuPersonas[card.modelData] || card.modelData
                                Keys.onReturnPressed: Jackson.setPersona(card.modelData)
                                Keys.onSpacePressed: Jackson.setPersona(card.modelData)

                                // radio: 1.5px lineStrong ring; on = a 5px `text` ring (components.css .radio)
                                Rectangle {
                                    id: radio

                                    x: 12
                                    y: 10
                                    width: 16
                                    height: 16
                                    radius: 8
                                    color: "transparent"
                                    border.width: card.isCurrent ? 5 : 1.5
                                    border.color: card.isCurrent ? Theme.selected : Theme.lineStrong
                                    antialiasing: true
                                }

                                Column {
                                    anchors.left: radio.right
                                    anchors.leftMargin: 10
                                    anchors.right: parent.right
                                    anchors.rightMargin: 10
                                    y: 8
                                    spacing: 1

                                    SText {
                                        width: parent.width
                                        text: Strings.cuPersonas[card.modelData] || card.modelData
                                        size: 13
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                        color: card.isCurrent ? Theme.text : Theme.textDim
                                    }
                                    MText {
                                        width: parent.width
                                        text: Strings.cuPersonaNotes[card.modelData] || ""
                                        size: 10.5
                                        elide: Text.ElideRight
                                        color: Theme.textFaint
                                    }
                                }

                                MouseArea {
                                    id: cardMouse

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: Jackson.setPersona(card.modelData)
                                }

                                FocusRing {
                                    radiusBase: 10
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---- footer --------------------------------------------------------------------------------------
        Item {
            width: parent.width
            height: 20
        }

        Divider {
            width: parent.width
        }

        Item {
            width: parent.width
            height: 60

            Row {
                x: 24
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                TextButton {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.changed
                    glyph: "undo-2"
                    text: Strings.cuRevert
                    onClicked: root.revert()
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.changed ? Strings.cuResetCmd : Strings.cuHint
                    size: 11
                    color: Theme.textFaint
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 24
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Button {
                    text: Strings.cuReset
                    onClicked: root.resetLook()
                }
                Button {
                    primary: true
                    text: Strings.wizDone
                    hint: "Enter"
                    onClicked: Ui.hide()
                }
            }
        }
    }
}
