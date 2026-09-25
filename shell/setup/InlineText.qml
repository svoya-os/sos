import QtQuick
import qs.core
import qs.components

// Paragraph with inline code chips (setup.css .wz-sub code: Plex Mono 12.5 in
// text color on surface3, 2px/5px padding, radius 5). Words flow and wrap;
// `<code>…</code>` becomes a chip. Default: Plex Sans 14/22 in textDim.
Flow {
    id: root

    property string text: ""
    property real size: 14
    property real lineHeight: 22
    property color color: Theme.textDim

    readonly property var tokens: {
        const out = [];
        const parts = root.text.split(/(<code>.*?<\/code>)/);
        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            if (part.indexOf("<code>") === 0) {
                out.push({ code: true, text: part.slice(6, part.length - 7) });
                continue;
            }
            const words = part.split(/(\s+)/);
            for (let j = 0; j < words.length; j++) {
                if (words[j].length > 0)
                    out.push({ code: false, text: /^\s+$/.test(words[j]) ? " " : words[j] });
            }
        }
        return out;
    }

    Repeater {
        model: root.tokens

        Item {
            required property var modelData

            width: modelData.code ? chip.width + 2 : word.implicitWidth
            height: root.lineHeight

            SText {
                id: word

                anchors.verticalCenter: parent.verticalCenter
                visible: !modelData.code
                text: modelData.code ? "" : modelData.text
                size: root.size
                color: root.color
            }

            Rectangle {
                id: chip

                x: 1
                anchors.verticalCenter: parent.verticalCenter
                visible: modelData.code
                width: code.implicitWidth + 10
                height: 18
                radius: 5
                color: Theme.surface3

                MText {
                    id: code

                    anchors.centerIn: parent
                    text: modelData.code ? modelData.text : ""
                    size: 12.5
                    color: Theme.text
                }
            }
        }
    }
}
