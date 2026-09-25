import QtQuick
import qs.core
import qs.components

// Step 6, page 2 of 2 · what Jackson thinks with (design/mockups/setup-ai.html, owner
// decision: ONE suggested model). Left: the detected GPU (or CPU) with RAM and GPU Doctor's
// verdict, then the model from `sos models suggest --json` with its fit bar and «Установить»
// → `sos models pull <id> --yes --json` (progress here and in the footer; the download keeps
// going when you move on). Right: optional cloud keys stored with `secret-tool` (never in
// files) and the cloud promise. Accent budget (DESIGN §11): the footer's «Дальше» is the one
// primary action; «Установить» is an outline button; only the running download is accent.
Item {
    id: root

    required property var wizard

    readonly property var s: root.wizard.suggest
    readonly property var hw: root.s && root.s.hardware ? root.s.hardware : null
    readonly property var d: root.s ? root.s["default"] : null
    readonly property bool cpu: !root.hw || root.hw.backend === "cpu"
    readonly property var gpu: Status.gpu
    readonly property real gib: 1073741824

    function gb(bytes) {
        return Fmt.smart(bytes / root.gib) + " " + Strings.gb;
    }

    readonly property real capacity: root.hw ? (root.cpu ? (root.hw.ramTotalBytes || 0) : (root.hw.memoryBytes || 0)) : 0
    readonly property string verdict: root.d ? root.d.verdict : ""
    readonly property color verdictColor: root.verdict === "fits" ? Theme.ok : (root.verdict === "offload" ? Theme.warn : Theme.bad)

    Row {
        spacing: 16

        // ---- left column -----------------------------------------------------------------------------------
        Column {
            width: 608
            spacing: 16

            // GPU / CPU
            Rectangle {
                width: parent.width
                height: gpuCol.height + 32
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Column {
                    id: gpuCol

                    x: 18
                    y: 16
                    width: parent.width - 36
                    spacing: 14

                    Item {
                        width: parent.width
                        height: Math.max(32, nameCol.height)

                        WizTile {
                            anchors.verticalCenter: parent.verticalCenter
                            glyph: root.cpu ? "cpu" : "svoya-gpu"
                        }
                        Column {
                            id: nameCol

                            x: 46
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 46 - doc.width - 16

                            SText {
                                width: parent.width
                                height: 20
                                elide: Text.ElideRight
                                text: root.cpu ? Strings.wzCpuOnly : (root.hw && root.hw.gpu ? root.hw.gpu : (root.gpu ? root.gpu.name : "…"))
                                size: 15
                                font.weight: Font.Medium
                            }
                            MText {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: {
                                    const parts = [];
                                    if (!root.cpu && root.capacity > 0)
                                        parts.push(root.gb(root.capacity));
                                    if (root.gpu && root.gpu.driver)
                                        parts.push(Strings.driver + " " + root.gpu.driver);
                                    if (root.hw && root.hw.ramTotalBytes)
                                        parts.push(Strings.wzRam + " " + root.gb(root.hw.ramTotalBytes));
                                    return parts.join(" · ");
                                }
                                size: 11
                                lineHeight: 16
                                lineHeightMode: Text.FixedHeight
                                color: Theme.textFaint
                            }
                        }
                        Row {
                            id: doc

                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 7
                            visible: root.wizard.doctor !== null && root.wizard.doctor.summary !== undefined

                            readonly property int issues: visible ? (root.wizard.doctor.summary.warn || 0) + (root.wizard.doctor.summary.fail || 0) : 0

                            Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                glyph: doc.issues === 0 ? "shield-check" : "triangle-alert"
                                size: 13
                                stroke: 2
                                color: doc.issues === 0 ? Theme.ok : Theme.warn
                            }
                            MText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: doc.issues === 0 ? Strings.wzDoctorOk : Strings.wzDoctorIssues(doc.issues)
                                size: 11
                                color: doc.issues === 0 ? Theme.ok : Theme.warn
                            }
                        }
                    }

                    // live video memory
                    Row {
                        width: parent.width
                        height: 11
                        spacing: 12
                        visible: root.gpu !== null && root.gpu.vramTotalMiB > 0

                        MText {
                            id: memLabel

                            anchors.verticalCenter: parent.verticalCenter
                            text: Strings.wzVram
                            size: 11
                            color: Theme.textFaint
                        }
                        WizBar {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - memLabel.width - memValue.width - 24
                            value: root.gpu && root.gpu.vramTotalMiB ? root.gpu.vramUsedMiB / root.gpu.vramTotalMiB : 0
                        }
                        MText {
                            id: memValue

                            anchors.verticalCenter: parent.verticalCenter
                            textFormat: Text.StyledText
                            text: root.gpu ? "<font color=\"" + Theme.textDim + "\">" + Fmt.gbFromMib(root.gpu.vramUsedMiB || 0) + "</font> / " + Fmt.gbFromMib(root.gpu.vramTotalMiB || 0) + " " + Strings.gb : ""
                            size: 11
                            color: Theme.textFaint
                        }
                    }
                }
            }

            // the suggested model
            Rectangle {
                width: parent.width
                height: 14 + 20 + 12 + 1 + 52 + 1 + 52
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                SText {
                    x: 18
                    y: 14
                    height: 20
                    text: Strings.wzModelFor
                    size: 14
                    font.weight: Font.Medium
                }
                MText {
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    y: 14
                    height: 20
                    text: root.cpu ? Strings.wzEstimateCpu : Strings.wzEstimate
                    size: 11
                    color: Theme.textFaint
                }

                Rectangle {
                    y: 46
                    width: parent.width
                    height: 1
                    color: Theme.line
                }

                // one row: radio · name · fit bar · size · verdict (grid 18 | 182 | 1fr | 62 | 172, gap 14)
                Item {
                    id: mrow

                    y: 47
                    width: parent.width
                    height: 52
                    visible: root.d !== null

                    WizCheck {
                        x: 18
                        anchors.verticalCenter: parent.verticalCenter
                        radio: true
                        checked: true
                    }
                    Column {
                        x: 18 + 18 + 14
                        width: 182
                        anchors.verticalCenter: parent.verticalCenter

                        MText {
                            width: parent.width
                            height: 16
                            elide: Text.ElideRight
                            text: root.d ? root.d.model : ""
                            size: 12.5
                            font.weight: Font.Medium
                            color: Theme.text
                        }
                        MText {
                            width: parent.width
                            height: 15
                            elide: Text.ElideRight
                            text: root.d ? root.d.quant + " · ≈ " + root.d.tokensPerSecond + " " + Strings.wzTokS : ""
                            size: 11
                            color: Theme.textFaint
                        }
                    }
                    WizBar {
                        x: 18 + 18 + 14 + 182 + 14
                        width: mrow.width - x - 14 - 62 - 14 - 172 - 18
                        anchors.verticalCenter: parent.verticalCenter
                        value: root.d && root.capacity > 0 ? root.d.memoryBytes8k / root.capacity : 0
                        fill: root.verdict === "fits" ? Theme.textDim : root.verdictColor
                    }
                    MText {
                        x: mrow.width - 18 - 172 - 14 - 62
                        width: 62
                        anchors.verticalCenter: parent.verticalCenter
                        horizontalAlignment: Text.AlignRight
                        text: root.d ? root.gb(root.d.sizeBytes) : ""
                        size: 12
                        color: Theme.textDim
                    }
                    Column {
                        x: mrow.width - 18 - 172
                        width: 172
                        anchors.verticalCenter: parent.verticalCenter

                        MText {
                            height: 15
                            text: root.verdict === "fits" ? Strings.wzFits : (root.verdict === "offload" ? Strings.wzTight : Strings.wzNoFit)
                            size: 11
                            color: root.verdictColor
                        }
                        MText {
                            width: parent.width
                            height: 15
                            elide: Text.ElideRight
                            text: {
                                if (!root.d)
                                    return "";
                                if (!root.d.diskOk)
                                    return Strings.wzNoDisk;
                                if (root.verdict === "offload")
                                    return Strings.wzOffloadNote;
                                if (root.verdict === "fits" && root.hw && root.capacity > 0)
                                    return Strings.wzLeftover(root.gb(Math.max(0, root.capacity - (root.hw.usedBytes || 0) - root.d.memoryBytes8k)));
                                return "";
                            }
                            size: 11
                            color: Theme.textFaint
                        }
                    }
                }

                MText {
                    x: 18
                    y: 47
                    height: 52
                    width: parent.width - 36
                    visible: root.d === null
                    wrapMode: Text.WordWrap
                    text: root.wizard.sosMissing ? Strings.wzNoSuggest : "…"
                    size: 11
                    color: Theme.textFaint
                }

                Rectangle {
                    y: 99
                    width: parent.width
                    height: 1
                    color: Theme.line
                }

                // install row
                Item {
                    y: 100
                    width: parent.width
                    height: 52
                    visible: root.d !== null

                    Button {
                        x: 18
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.wizard.pullState === "idle" || root.wizard.pullState === "error"
                        small: true
                        glyph: "download"
                        text: root.wizard.pullState === "error" ? Strings.wzRetry : Strings.wzInstallModel
                        enabledState: root.d !== null && root.d.diskOk
                        onClicked: root.wizard.pullModel()
                    }

                    Row {
                        x: 18
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12
                        visible: root.wizard.pullState === "running"

                        WizBar {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 220
                            cap: false
                            fill: Theme.accent // a running job: the live signal
                            value: root.wizard.pullFraction
                        }
                        MText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Fmt.bytes(root.wizard.pullBytes) + " / " + Fmt.bytes(root.wizard.pullTotal) + " · " + Math.round(root.wizard.pullFraction * 100) + "%"
                            size: 11
                            color: Theme.textDim
                        }
                        Button {
                            anchors.verticalCenter: parent.verticalCenter
                            small: true
                            text: Strings.cancel
                            onClicked: root.wizard.cancelPull()
                        }
                    }

                    Row {
                        x: 18
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 7
                        visible: root.wizard.pullState === "done"

                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            glyph: "check"
                            size: 13
                            stroke: 2.2
                            color: Theme.ok
                        }
                        MText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Strings.wzInstalled
                            size: 11
                            color: Theme.ok
                        }
                    }

                    MText {
                        anchors.right: parent.right
                        anchors.rightMargin: 18
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, parent.width - 200)
                        elide: Text.ElideRight
                        text: root.wizard.pullState === "error" ? root.wizard.pullError : (root.wizard.pullState === "idle" ? Strings.wzDownloadTo : "")
                        size: 11
                        color: root.wizard.pullState === "error" ? Theme.bad : Theme.textFaint
                    }
                }
            }
        }

        // ---- right column: cloud keys + the promise ------------------------------------------------------------
        Column {
            width: 1040 - 608 - 16
            spacing: 16

            Rectangle {
                width: parent.width
                height: 14 + 20 + 4 + cloudSub.height + 12 + root.wizard.providers.length * 47
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Row {
                    x: 18
                    y: 14
                    height: 20
                    spacing: 10

                    SText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.wzCloud
                        size: 14
                        font.weight: Font.Medium
                    }
                    WizTag {
                        anchors.verticalCenter: parent.verticalCenter
                        kind: "line"
                        text: Strings.wzOptional
                    }
                }

                SText {
                    id: cloudSub

                    x: 18
                    y: 38
                    width: parent.width - 36
                    text: Strings.wzCloudSub
                    size: 12.5
                    lineHeight: 19
                    lineHeightMode: Text.FixedHeight
                    wrapMode: Text.WordWrap
                    color: Theme.textDim
                }

                Column {
                    y: cloudSub.y + cloudSub.height + 12
                    width: parent.width

                    Repeater {
                        model: root.wizard.providers

                        Item {
                            id: prow

                            required property var modelData
                            property bool adding: false
                            property string failed: ""
                            readonly property bool saved: root.wizard.keys[modelData.id] === true

                            width: parent.width
                            height: 47

                            Rectangle {
                                width: parent.width
                                height: 1
                                color: Theme.line
                            }

                            Column {
                                x: 18
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: 0.5
                                visible: !prow.adding

                                SText {
                                    height: 16
                                    text: prow.modelData.name
                                    size: 13
                                    font.weight: Font.Medium
                                }
                                MText {
                                    height: 15
                                    text: prow.failed.length > 0 ? prow.failed : prow.modelData.sub
                                    size: 11
                                    color: prow.failed.length > 0 ? Theme.bad : Theme.textFaint
                                }
                            }

                            Row {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: 0.5
                                spacing: 6
                                visible: prow.saved && !prow.adding

                                Icon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    glyph: "check"
                                    size: 12
                                    stroke: 2.2
                                    color: Theme.ok
                                }
                                MText {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Strings.wzKeyInRing
                                    size: 11
                                    color: Theme.ok
                                }
                            }

                            Button {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: 0.5
                                visible: !prow.saved && !prow.adding && Sys.has["secret-tool"] === true
                                small: true
                                text: Strings.wzAddKey
                                onClicked: {
                                    prow.failed = "";
                                    prow.adding = true;
                                    keyField.focusInput();
                                }
                            }

                            // inline key entry: masked, sent to secret-tool on stdin
                            Row {
                                x: 18
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: 0.5
                                spacing: 8
                                visible: prow.adding

                                Rectangle {
                                    width: prow.width - 36 - saveBtn.width - closeKey.width - 16
                                    height: 30
                                    radius: 7
                                    color: Theme.surface2
                                    border.width: 1
                                    border.color: keyField.input.activeFocus ? Theme.text : Theme.lineStrong

                                    TextField {
                                        id: keyField

                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        size: 12.5
                                        password: true
                                        placeholder: prow.modelData.name + " · " + Strings.wzPasteKey
                                        onAccepted: saveBtn.clicked()
                                        onEscapePressed: prow.adding = false
                                    }
                                }
                                Button {
                                    id: saveBtn

                                    anchors.verticalCenter: parent.verticalCenter
                                    small: true
                                    text: Strings.wzSave
                                    enabledState: keyField.text.trim().length > 8
                                    onClicked: {
                                        if (keyField.text.trim().length <= 8)
                                            return;
                                        const key = keyField.text;
                                        keyField.text = "";
                                        prow.adding = false;
                                        root.wizard.storeKey(prow.modelData.id, key, ok => {
                                            prow.failed = ok ? "" : Strings.wizKeyFailed;
                                        });
                                    }
                                }
                                Icon {
                                    id: closeKey

                                    anchors.verticalCenter: parent.verticalCenter
                                    glyph: "x"
                                    size: 14

                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.margins: -6
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            keyField.text = "";
                                            prow.adding = false;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // the promise
            Rectangle {
                width: parent.width
                height: noteCol.height + 30
                radius: 14
                color: Theme.isDark ? Theme.surface : Theme.surface2
                border.width: 1
                border.color: Theme.line

                Icon {
                    x: 18
                    y: 15
                    glyph: "svoya-shield"
                    size: 18
                    stroke: 1.6
                    color: Theme.textDim
                }
                Column {
                    id: noteCol

                    x: 48
                    y: 14
                    width: parent.width - 48 - 18
                    spacing: 3

                    SText {
                        height: 19
                        text: Strings.wzCloudNoteTitle
                        size: 13
                        font.weight: Font.Medium
                    }
                    SText {
                        width: parent.width
                        text: Strings.wzCloudNote
                        size: 12.5
                        lineHeight: 19
                        lineHeightMode: Text.FixedHeight
                        wrapMode: Text.WordWrap
                        color: Theme.textDim
                    }
                }
            }
        }
    }
}
