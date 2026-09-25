import QtQuick
import qs.core
import qs.components

// Inline approval request (DESIGN.md §5): what Jackson wants to do, the exact
// preview (text or diff) and three buttons: «Разрешить один раз» ·
// «Всегда в этом проекте» · «Отклонить». Nothing is focused automatically:
// approving is always a deliberate Tab + Enter or a click.
Rectangle {
    id: root

    property var request: ({})    // {callId, name, preview, tier}
    readonly property int tier: Number(root.request.tier || 2)

    implicitHeight: col.implicitHeight + 28
    radius: 12
    color: Theme.surface
    border.width: 1
    border.color: root.tier >= 3 ? Theme.warn : Theme.lineStrong

    function focusFirst() {
        once.forceActiveFocus();
    }

    Column {
        id: col

        x: 14
        y: 14
        width: parent.width - 28
        spacing: 10

        Row {
            spacing: 8

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: tierLabel.implicitWidth + 12
                height: 18
                radius: 9
                color: root.tier >= 3 ? Theme.alpha(Theme.warn, 0.14) : Theme.surface3

                MText {
                    id: tierLabel

                    anchors.centerIn: parent
                    text: "T" + root.tier + " · " + (Strings.tierNames[root.tier] || "")
                    size: 10.5
                    color: root.tier >= 3 ? Theme.warn : Theme.textDim
                }
            }

            SText {
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.approvalTitle
                size: 13
                font.weight: Font.Medium
            }

            MText {
                anchors.verticalCenter: parent.verticalCenter
                text: root.request.name || ""
                size: 11
                color: Theme.textFaint
            }
        }

        CodeBlock {
            width: parent.width
            text: typeof root.request.preview === "string" ? root.request.preview : JSON.stringify(root.request.preview, null, 2)
            maxHeight: 200
        }

        Row {
            spacing: 8

            Button {
                id: once

                primary: true
                text: Strings.approveOnce
                onClicked: Jackson.approve(root.request.callId, "once")
            }
            Button {
                text: Strings.approveAlways
                onClicked: Jackson.approve(root.request.callId, "always-project")
            }
            Button {
                text: Strings.deny
                danger: true
                onClicked: Jackson.approve(root.request.callId, "deny")
            }
        }
    }
}
