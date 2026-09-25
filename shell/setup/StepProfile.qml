import QtQuick
import qs.core
import qs.components

// Step 5 · profile (design/mockups/setup-profile.html) + apps. Profiles come
// from `sos modules profiles --json` (module sets; "@gpu" already resolved),
// names and sizes from `sos modules list --json`. Nothing installs here: the
// choice is queued and installed after the wizard closes (administrator
// prompt), with a snapshot first. Obsidian is pre-checked (module "notes"); games (module
// "gaming": Steam, GameMode, MangoHud) are one switch next to it.
Item {
    id: root

    required property var wizard

    readonly property var icons: ({ newcomer: "svoya-compass", creator: "svoya-aperture", ml: "svoya-flask", agent: "svoya-nodes", hacker: "terminal" })
    readonly property real gpuGb: {
        const g = Status.gpu;
        if (g && g.vramTotalMiB)
            return g.vramTotalMiB / 1024;
        const s = root.wizard.suggest;
        return s && s.hardware && s.hardware.memoryBytes ? s.hardware.memoryBytes / 1073741824 : 0;
    }

    function pick(v) {
        if (!v)
            return "";
        if (typeof v === "string")
            return v;
        return (Strings.ru ? v.ru : v.en) || v.en || v.ru || "";
    }

    function moduleLabel(id) {
        const m = root.wizard.catalog[id];
        return m ? root.pick(m.name) : id;
    }

    function minutes(gb) {
        return Math.max(1, Math.round(1 + gb * 0.4));
    }

    function vramNeed(mods) {
        let need = 0;
        for (let i = 0; i < mods.length; i++) {
            const m = root.wizard.catalog[mods[i]];
            if (m && m.vramGbMin)
                need = Math.max(need, Number(m.vramGbMin));
        }
        return need;
    }

    readonly property var chosen: root.wizard.profiles.find(p => p.id === root.wizard.profile) || null
    readonly property real queuedGb: {
        let gb = 0;
        const q = root.wizard.queuedModules;
        for (let i = 0; i < q.length; i++) {
            const m = root.wizard.catalog[q[i]];
            gb += m && m.diskGb ? Number(m.diskGb) : 0;
        }
        return gb;
    }

    Grid {
        id: grid

        columns: 3
        columnSpacing: 16
        rowSpacing: 16
        visible: root.wizard.profiles.length > 0

        Repeater {
            model: root.wizard.profiles.slice(0, 5)

            WizCard {
                id: card

                required property var modelData
                readonly property real need: root.vramNeed(modelData.modules || [])

                width: 336
                height: 186
                selected: root.wizard.profile === modelData.id
                onPicked: root.wizard.profile = modelData.id

                WizTile {
                    x: 18
                    y: 18
                    glyph: root.icons[card.modelData.id] || "box"
                    accent: card.selected
                }
                SText {
                    x: 62
                    y: 24
                    height: 20
                    width: card.width - 62 - 48
                    elide: Text.ElideRight
                    text: root.pick(card.modelData.name)
                    size: 15
                    font.weight: Font.Medium
                }
                WizCheck {
                    x: card.width - 18 - width
                    y: 25
                    checked: card.selected
                }
                SText {
                    x: 18
                    y: 62
                    width: card.width - 36
                    text: root.pick(card.modelData.summary)
                    size: 13
                    lineHeight: 20
                    lineHeightMode: Text.FixedHeight
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    color: Theme.textDim
                }
                Flow {
                    x: 18
                    y: 127
                    width: card.width - 36
                    height: 20
                    spacing: 6
                    clip: true

                    Repeater {
                        // the foundation and the driver are implied: show what the profile adds
                        model: (card.modelData.modules || []).filter(m => ["base-ai", "nvidia", "rocm", "codecs"].indexOf(m) < 0)

                        WizTag {
                            required property string modelData

                            text: root.moduleLabel(modelData)
                        }
                    }
                }
                MText {
                    x: 18
                    y: 159
                    height: 11
                    textFormat: Text.StyledText
                    text: "<font color=\"" + Theme.textDim + "\">" + Fmt.smart(card.modelData.diskGb || 0) + " " + Strings.gb + "</font> · " + root.minutes(card.modelData.diskGb || 0) + (Strings.ru ? " мин" : " min")
                    size: 11
                    color: Theme.textFaint
                }
                Row {
                    x: card.width - 18 - width
                    y: 159
                    height: 11
                    spacing: 5
                    visible: card.need > 0 && root.gpuGb > 0

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        glyph: root.gpuGb >= card.need ? "check" : "triangle-alert"
                        size: 11
                        stroke: 2.4
                        color: root.gpuGb >= card.need ? Theme.ok : Theme.warn
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.gpuGb >= card.need ? Strings.wzGpuFits : Strings.wzGpuShort
                        size: 11
                        color: root.gpuGb >= card.need ? Theme.ok : Theme.warn
                    }
                }
            }
        }

        // the «offline only» modifier: dashed card with a switch
        WizCard {
            id: offlineCard

            width: 336
            height: 186
            dashed: true
            clickable: false

            WizTile {
                x: 18
                y: 18
                glyph: "cloud-off"
            }
            SText {
                x: 62
                y: 24
                height: 20
                text: Strings.profOffline
                size: 15
                font.weight: Font.Medium
            }
            Toggle {
                x: offlineCard.width - 18 - width
                y: 25
                checked: root.wizard.offline
                onToggled: value => root.wizard.offline = value
            }
            SText {
                x: 18
                y: 62
                width: offlineCard.width - 36
                text: Strings.t("Никаких облачных моделей и сетевых запросов от ИИ. Модули — с флешки или из зеркала.", "No cloud models and no network requests from AI. Modules from a USB stick or a mirror.")
                size: 13
                lineHeight: 20
                lineHeightMode: Text.FixedHeight
                wrapMode: Text.WordWrap
                color: Theme.textDim
            }
            MText {
                x: 18
                y: 159
                height: 11
                text: Strings.wzOfflineFoot
                size: 11
                color: Theme.textFaint
            }
        }
    }

    MText {
        visible: root.wizard.profiles.length === 0
        width: parent.width
        wrapMode: Text.WordWrap
        text: Strings.wizCatalogMissing
        size: 12
        color: Theme.textDim
    }

    // ---- summary -------------------------------------------------------------------------------------------
    Rectangle {
        id: summary

        y: grid.visible ? grid.height + 20 : 40
        width: parent.width
        height: 48
        radius: 14
        color: Theme.isDark ? Theme.surface : Theme.surface2
        border.width: 1
        border.color: Theme.line

        Icon {
            x: 18
            anchors.verticalCenter: parent.verticalCenter
            glyph: "package"
            size: 18
        }
        SText {
            x: 50
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 50 - summaryRight.width - 36
            elide: Text.ElideRight
            textFormat: Text.StyledText
            text: root.wizard.queuedModules.length === 0 ? Strings.wzNothingToInstall : Strings.wzWillInstall + " <font color=\"" + Theme.text + "\"><b>" + root.wizard.queuedModules.map(id => root.moduleLabel(id)).join(", ") + "</b></font>. " + Strings.wzBeforeInstall
            size: 13
            color: Theme.textDim
        }
        Row {
            id: summaryRight

            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 18
            visible: root.wizard.queuedModules.length > 0

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 5

                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Fmt.smart(root.queuedGb) + " " + Strings.gb
                    size: 13
                    font.weight: Font.Medium
                    color: Theme.text
                }
                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    // !!: `null && …` would assign null to a bool (binding error, stays visible)
                    visible: !!(root.wizard.suggest && root.wizard.suggest.hardware && root.wizard.suggest.hardware.diskFreeBytes)
                    text: visible ? Strings.wzFreeOf(Fmt.bytes(root.wizard.suggest.hardware.diskFreeBytes)) : ""
                    size: 11
                    color: Theme.textFaint
                }
            }
            MText {
                anchors.verticalCenter: parent.verticalCenter
                text: "≈ " + root.minutes(root.queuedGb) + (Strings.ru ? " мин" : " min")
                size: 13
                font.weight: Font.Medium
                color: Theme.text
            }
        }
    }

    // ---- apps: Obsidian (pre-checked) and games, side by side ------------------------------------------------
    component AppRow: Rectangle {
        id: row

        property string glyph: ""
        property string title: ""
        property string sub: ""
        property string moduleId: ""
        property bool want: false
        readonly property bool present: !!(root.wizard.catalog[row.moduleId] && root.wizard.catalog[row.moduleId].installed)

        signal flipped(bool value)

        height: 60
        radius: 14
        color: Theme.isDark ? Theme.surface : Theme.surface2
        border.width: 1
        border.color: Theme.line

        WizTile {
            x: 14
            anchors.verticalCenter: parent.verticalCenter
            glyph: row.glyph
            accent: row.want || row.present
        }
        Column {
            x: 60
            width: parent.width - 60 - 76
            anchors.verticalCenter: parent.verticalCenter

            SText {
                height: 18
                width: parent.width
                elide: Text.ElideRight
                text: row.title
                size: 13
                font.weight: Font.Medium
            }
            MText {
                height: 16
                width: parent.width
                elide: Text.ElideRight
                text: row.present ? row.sub + " · " + Strings.installed : row.sub
                size: 11
                color: Theme.textFaint
            }
        }
        Toggle {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            enabled: !row.present
            checked: row.want || row.present
            onToggled: value => row.flipped(value)
        }
    }

    Row {
        y: summary.y + summary.height + 12
        width: parent.width
        spacing: 12

        AppRow {
            width: (parent.width - 12) / 2
            glyph: "file-text"
            title: "Obsidian"
            sub: Strings.wzObsidianSub
            moduleId: "notes"
            want: root.wizard.obsidian
            onFlipped: value => root.wizard.obsidian = value
        }
        AppRow {
            width: (parent.width - 12) / 2
            glyph: "gamepad-2"
            title: Strings.wzGames
            sub: Strings.wzGamesSub
            moduleId: "gaming"
            want: root.wizard.gaming
            onFlipped: value => root.wizard.gaming = value
        }
    }
}
