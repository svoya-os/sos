import QtQuick
import qs.core
import qs.components

// After a region screenshot (Super+Shift+S): the shot and what to do with it.
// J ask Jackson (the image goes as context.screenshot) · C copy · T extract
// text (tesseract if installed; otherwise a calm stub) · S save to Pictures.
PanelFrame {
    id: root

    readonly property string path: Ui.shotPath

    function askJackson() {
        Jackson.screenshot = root.path;
        Ui.show("jackson");
    }

    function copy() {
        Sys.sh('wl-copy --type image/png < "$1"', [root.path], function (code) {
            if (code === 0)
                Notifs.shellToast(Strings.copied, "", "copy");
        });
        Ui.hide();
    }

    function ocr() {
        Ui.hide();
        if (!Sys.has["tesseract"]) {
            Notifs.shellToast(Strings.extractText, Strings.ocrMissing, "scan-text");
            return;
        }
        Sys.sh('tesseract "$1" - -l rus+eng 2>/dev/null | wl-copy', [root.path], function (code) {
            Notifs.shellToast(code === 0 ? Strings.textCopied : Strings.extractText, code === 0 ? "" : Strings.ocrMissing, "scan-text");
        });
    }

    function save() {
        const dir = Sys.home + "/" + Strings.t("Изображения", "Pictures") + "/Screenshots";
        const name = "SOS-" + Qt.formatDateTime(new Date(), "yyyy-MM-dd-HHmmss") + ".png";
        Sys.sh('d="$2"; [ -d "$(dirname "$d")" ] || d="$HOME/Pictures/Screenshots"; mkdir -p "$d" && cp "$1" "$d/$3" && echo "$d/$3"', [root.path, dir, name], function (code, out) {
            if (code === 0)
                Notifs.shellToast(Strings.savedTo(out.trim().replace(Sys.home, "~")), "", "download");
        });
        Ui.hide();
    }

    width: 560
    implicitHeight: col.implicitHeight

    onShownChanged: {
        if (root.shown)
            Qt.callLater(() => keys.forceActiveFocus());
    }

    Item {
        id: keys

        focus: true
        Keys.onEscapePressed: Ui.hide()
        Keys.onReturnPressed: Jackson.enabled ? root.askJackson() : root.copy()
        Keys.onPressed: event => {
            if (event.key === Qt.Key_J && Jackson.enabled)
                root.askJackson();
            else if (event.key === Qt.Key_C)
                root.copy();
            else if (event.key === Qt.Key_T)
                root.ocr();
            else if (event.key === Qt.Key_S)
                root.save();
            else
                return;
            event.accepted = true;
        }
    }

    Column {
        id: col

        width: parent.width
        padding: 18
        spacing: 14

        Rectangle {
            width: parent.width - 36
            height: Math.min(280, Math.max(80, shot.implicitHeight > 0 ? (width - 2) * shot.implicitHeight / Math.max(1, shot.implicitWidth) + 2 : 160))
            radius: Theme.radiusBlock
            color: Theme.surface
            border.width: 1
            border.color: Theme.line
            clip: true

            Image {
                id: shot

                anchors.fill: parent
                anchors.margins: 1
                source: root.path.length > 0 ? "file://" + root.path : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
            }
        }

        Flow {
            width: parent.width - 36
            spacing: 8

            Button {
                visible: Jackson.enabled
                primary: true
                glyph: "sparkles"
                text: Strings.askJackson
                hint: "J"
                onClicked: root.askJackson()
            }
            Button {
                primary: !Jackson.enabled
                glyph: "copy"
                text: Strings.copy
                hint: "C"
                onClicked: root.copy()
            }
            Button {
                glyph: "scan-text"
                text: Strings.extractText
                hint: "T"
                onClicked: root.ocr()
            }
            Button {
                glyph: "download"
                text: Strings.save
                hint: "S"
                onClicked: root.save()
            }
        }
    }
}
