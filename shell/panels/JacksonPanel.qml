import QtQuick
import qs.core
import qs.components
import "Markdown.js" as Md

// Jackson panel (Super+J; DESIGN.md §5, design/mockups/desktop.html):
// width 704, top 118, centered, radius 16, surface2, lineStrong border, accent
// top highlight (the panel is `live`). Head: the 32px mascot · name · route chip ·
// scope (92×22) · keycaps Super J.
// Input: Plex Sans 20 with the 2px accent caret. Answer: streamed Markdown
// (14.2/1.6), tables in a bordered mono block, approvals inline, actions.
// Footer 40px: latency · tokens · cost € · local/cloud statement | Tab, Esc.
//
// Keys: Enter asks (or runs the primary action when the question is
// unchanged), Shift+Enter new line, Tab refines the answer (moves focus to
// approval buttons while one is pending), Up recalls the last question,
// Ctrl+C stops a running turn, Esc closes.
PanelFrame {
    id: root

    property bool refining: false
    property int tip: 0                   // which example the empty field suggests (a new one each time)
    property var blocks: []
    readonly property bool hasTurn: Jackson.turnId.length > 0 || Jackson.error !== null
    readonly property var route: Jackson.shownRoute
    readonly property var actions: {
        const out = [];
        for (let i = 0; i < root.blocks.length; i++) {
            if (root.blocks[i].type === "actions")
                return root.blocks[i].items;
        }
        return Jackson.suggestions || out;
    }

    function focusInput() {
        input.forceActiveFocus();
        input.cursorPosition = input.length;
    }

    function submit() {
        const text = input.text.trim();
        if (text.length === 0)
            return;
        if (!root.refining && text === Jackson.question && !Jackson.busy) {
            root.runAction(0);
            return;
        }
        const refines = root.refining ? Jackson.turnId : "";
        if (Jackson.ask(text, refines))
            root.refining = false;
    }

    function runAction(index) {
        const list = root.actions;
        if (!list || list.length === 0)
            return;
        let pick = list[index];
        for (let i = 0; i < list.length; i++) {
            if (list[i].primary && index === 0)
                pick = list[i];
        }
        if (!pick)
            return;
        const text = pick.prompt || pick.label || "";
        input.text = text;
        Jackson.ask(text, Jackson.turnId);
    }

    width: 704
    implicitHeight: col.implicitHeight
    live: true

    onShownChanged: {
        if (root.shown) {
            root.tip = Math.floor(Math.random() * 1000);
            if (!Jackson.busy && Jackson.question.length > 0 && input.text.length === 0)
                input.text = Jackson.question;
            avatar.warmUp();
            if (headScope.visible)
                headScope.warmUp();
            Qt.callLater(root.focusInput);
            if (Jackson.connected)
                Jackson.requestStatus();
        }
    }

    // Streaming: re-parse at most ~30 times per second and update only the
    // blocks that changed (ListModel.set keeps the other delegates alive).
    function reparse() {
        const list = Md.parse(Jackson.answer);
        root.blocks = list;
        for (let i = 0; i < list.length; i++) {
            const payload = JSON.stringify(list[i]);
            if (i < blockModel.count) {
                if (blockModel.get(i).payload !== payload)
                    blockModel.set(i, { kind: list[i].type, payload: payload });
            } else {
                blockModel.append({ kind: list[i].type, payload: payload });
            }
        }
        while (blockModel.count > list.length)
            blockModel.remove(blockModel.count - 1);
    }

    ListModel {
        id: blockModel
    }

    Connections {
        target: Jackson

        function onAnswerChanged() {
            if (!parseTimer.running)
                parseTimer.start();
        }
        function onTurnIdChanged() {
            root.reparse();
        }
    }

    Timer {
        id: parseTimer

        interval: 33
        onTriggered: root.reparse()
    }

    Column {
        id: col

        width: parent.width

        // ---- head: mascot · name · route chip ……… scope · Super J --------------------------------
        Item {
            width: parent.width
            height: 14 + 32
            z: 2 // the mascot's right-click menu opens over the input below

            Row {
                x: 16
                y: 14
                height: 32
                spacing: 12

                JacksonAvatar {
                    id: avatar

                    anchors.verticalCenter: parent.verticalCenter
                    size: 32
                    live: root.shown
                }

                SText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Jackson.name
                    size: 13
                    font.weight: Font.Medium
                    font.letterSpacing: 0.13
                }

                Chip {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: text.length > 0
                    dotColor: !Jackson.connected ? Theme.textFaint : (root.route && !root.route.local ? Theme.cloud : Theme.ok)
                    text: {
                        if (Jackson.mode === "off")
                            return Strings.jacksonDisabled;
                        if (!Jackson.connected)
                            return Strings.jacksonOffline;
                        const r = root.route;
                        if (!r)
                            return Strings.local;
                        if (r.local)
                            return Strings.local + (r.model ? " · " + r.model : "");
                        return Strings.cloud + " · " + (r.provider || r.label || r.model);
                    }
                }

                Chip {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: Jackson.screenshot.length > 0
                    showDot: false
                    text: "▣ " + Strings.screenshotAttached
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 18
                y: 14
                height: 32
                spacing: 12

                // the scope: Jackson's live signal (the mascot's stand-in when there is no sprite)
                Oscilloscope {
                    id: headScope

                    anchors.verticalCenter: parent.verticalCenter
                    visible: avatar.hasSprite
                    width: 92
                    height: 22
                    mode: Jackson.mode === "off" || Jackson.mode === "offline" ? "idle" : Jackson.mode
                    live: root.shown
                    opacity: Jackson.mode === "offline" || Jackson.mode === "off" ? 0.5 : 1
                }

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Super"
                    }
                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "J"
                    }
                }
            }
        }

        // ---- input ---------------------------------------------------------------------------
        Item {
            width: parent.width
            height: Math.max(input.contentHeight, 27.6) + 16 + 18

            TextEdit {
                id: input

                x: 18
                y: 16
                width: parent.width - 36
                wrapMode: TextEdit.Wrap
                color: Theme.text
                selectionColor: Theme.accentSoft
                selectedTextColor: Theme.text
                font.family: Theme.sans
                font.pixelSize: Theme.fsTitle * Theme.textScale
                font.features: Theme.sansFeatures
                font.letterSpacing: -0.1
                textFormat: TextEdit.PlainText
                enabled: Jackson.mode !== "off"
                focus: true
                persistentSelection: false
                cursorDelegate: Rectangle {
                    width: 2
                    color: Theme.accent
                    visible: input.activeFocus
                }

                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        if (event.modifiers & Qt.ShiftModifier)
                            return; // newline
                        root.submit();
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Escape) {
                        Ui.hide();
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Tab) {
                        if (Jackson.approvals.length > 0) {
                            approvals.itemAt(0).focusFirst();
                        } else if (root.hasTurn) {
                            root.refining = true;
                            input.text = "";
                        }
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Up && input.text.length === 0 && Jackson.lastText.length > 0) {
                        input.text = Jackson.lastText;
                        input.cursorPosition = input.length;
                        event.accepted = true;
                    } else if (event.key === Qt.Key_C && (event.modifiers & Qt.ControlModifier) && Jackson.busy && input.selectedText.length === 0) {
                        Jackson.cancel();
                        event.accepted = true;
                    }
                }
            }

            SText {
                x: 18
                y: 16
                width: parent.width - 36
                visible: input.text.length === 0
                text: Jackson.mode === "off" ? Strings.jacksonDisabled : (root.refining ? Strings.jacksonRefinePlaceholder : (Jackson.screenshot.length > 0 ? Strings.jacksonShotPlaceholder : Strings.jacksonPlaceholderTip(root.tip)))
                size: Theme.fsTitle
                scaled: true
                color: Theme.textFaint
                elide: Text.ElideRight
            }
        }

        // ---- answer ---------------------------------------------------------------------------
        Item {
            width: parent.width
            height: visible ? answerFlick.height + 1 : 0
            visible: root.hasTurn || !Jackson.connected

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.line
            }

            Flickable {
                id: answerFlick

                y: 1
                width: parent.width
                height: Math.min(answer.implicitHeight, Math.max(160, (root.parent ? root.parent.height : 900) - 118 - 220))
                contentHeight: answer.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                // follow the stream while the user has not scrolled up
                property bool follow: true
                onContentHeightChanged: {
                    if (follow && contentHeight > height)
                        contentY = contentHeight - height;
                }
                onMovementEnded: follow = contentY >= contentHeight - height - 4

                Column {
                    id: answer

                    x: 18
                    width: parent.width - 36
                    spacing: 14
                    topPadding: 16
                    bottomPadding: 18

                    // offline / off
                    SText {
                        visible: !Jackson.connected && !root.hasTurn
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: Jackson.mode === "off" ? Strings.jacksonDisabled : Strings.jacksonOfflineBody
                        size: Theme.fsAnswer
                        scaled: true
                        color: Theme.textDim
                        lineHeight: 1.6
                    }

                    Column {
                        width: parent.width
                        spacing: 6
                        visible: Jackson.tools.length > 0

                        Repeater {
                            model: Jackson.tools

                            ToolRow {
                                required property var modelData

                                call: modelData
                            }
                        }
                    }

                    Repeater {
                        model: blockModel

                        Loader {
                            required property string kind
                            required property string payload
                            readonly property var block: JSON.parse(payload)

                            width: answer.width
                            sourceComponent: kind === "md" ? mdBlock : kind === "table" ? tableBlock : kind === "code" ? codeBlock : kind === "fit" ? fitBlock : null
                        }
                    }

                    Repeater {
                        id: approvals

                        model: Jackson.approvals

                        ApprovalCard {
                            required property var modelData

                            width: answer.width
                            request: modelData
                        }
                    }

                    // error, calm and concrete. No model yet is not a failure on a fresh system: plain
                    // text and one button that picks the model for this machine (the fast path answers)
                    Row {
                        readonly property bool noModel: Jackson.error !== null && Jackson.error.code === "no_local_model"

                        visible: Jackson.error !== null
                        spacing: 12

                        SText {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(implicitWidth, answer.width - (parent.noModel ? 190 : 120))
                            wrapMode: Text.WordWrap
                            text: Jackson.error ? Jackson.error.message : ""
                            size: 13.5
                            color: parent.noModel ? Theme.textDim : Theme.bad
                        }

                        Button {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: parent.noModel
                            small: true
                            primary: true
                            text: Strings.pickModel
                            onClicked: Jackson.ask(Strings.pickModelAsk)
                        }

                        Button {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: Jackson.error !== null && Jackson.error.retryable && !parent.noModel
                            small: true
                            text: Strings.retry
                            onClicked: Jackson.retry()
                        }
                    }

                    // actions: primary (accent) + secondary (outline)
                    Row {
                        visible: root.actions.length > 0 && !Jackson.busy
                        spacing: 8

                        Repeater {
                            model: root.actions

                            Button {
                                required property var modelData
                                required property int index

                                primary: modelData.primary === true || (index === 0 && root.actions.every(a => !a.primary))
                                text: modelData.label || ""
                                hint: primary ? "Enter" : ""
                                onClicked: root.runAction(index)
                            }
                        }
                    }
                }
            }
        }

        // ---- footer ------------------------------------------------------------------------------
        Item {
            width: parent.width
            height: 40

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.line
            }

            Row {
                x: 18
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: 0.5
                spacing: 8

                Dot {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: Jackson.result !== null
                    color: Jackson.result && Jackson.result.leftMachine ? Theme.cloud : Theme.ok
                }

                MText {
                    anchors.verticalCenter: parent.verticalCenter
                    size: 11
                    color: Theme.textFaint
                    text: {
                        const r = Jackson.result;
                        if (!r) {
                            if (Jackson.busy)
                                return Jackson.mode === "listening" ? Strings.jacksonListening : Strings.jacksonThinking;
                            return "";
                        }
                        const parts = [];
                        if (r.latencyMs !== undefined)
                            parts.push(Strings.seconds(r.latencyMs));
                        const u = r.usage || {};
                        const tokens = (Number(u.inTokens) || 0) + (Number(u.outTokens) || 0);
                        if (tokens > 0)
                            parts.push(Strings.tokens(tokens));
                        parts.push(Strings.euro(r.costEur || 0));
                        parts.push(r.leftMachine ? Strings.dataLeft(Jackson.route ? Jackson.route.provider : "") : Strings.dataStayed);
                        return parts.join(" · ");
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14

                Row {
                    spacing: 6
                    visible: Jackson.busy

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Ctrl C"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.stop
                        size: 11
                        color: Theme.textFaint
                    }
                }

                Row {
                    spacing: 6
                    visible: root.hasTurn && !Jackson.busy

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Tab"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.refine
                        size: 11
                        color: Theme.textFaint
                    }
                }

                Row {
                    spacing: 6

                    Keycap {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Esc"
                    }
                    MText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Strings.close
                        size: 11
                        color: Theme.textFaint
                    }
                }
            }
        }
    }

    // ---- block components -------------------------------------------------------------------------
    Component {
        id: mdBlock

        SText {
            // the Loader that hosts this block
            readonly property var block: parent && parent.block ? parent.block : ({})

            text: block.text || ""
            textFormat: Text.MarkdownText
            wrapMode: Text.WordWrap
            size: Theme.fsAnswer
            scaled: true
            lineHeight: 1.6
            color: Theme.text
            linkColor: Theme.accent
            onLinkActivated: link => Sys.openUrl(link)
        }
    }

    Component {
        id: tableBlock

        MdTable {
            // the Loader that hosts this block
            readonly property var block: parent && parent.block ? parent.block : ({})

            header: block.header || []
            rows: block.rows || []
        }
    }

    Component {
        id: codeBlock

        CodeBlock {
            // the Loader that hosts this block
            readonly property var block: parent && parent.block ? parent.block : ({})

            text: block.text || ""
            lang: block.lang || ""
        }
    }

    Component {
        id: fitBlock

        FitTable {
            // the Loader that hosts this block
            readonly property var block: parent && parent.block ? parent.block : ({})

            rows: block.rows || []
            capacityGb: block.capacityGb ? block.capacityGb : (Status.gpu && Status.gpu.vramTotalMiB ? Status.gpu.vramTotalMiB / 1024 : 0)
        }
    }
}
