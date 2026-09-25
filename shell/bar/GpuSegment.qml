import QtQuick
import qs.core

// «GPU 64° · 11,2/24 ГБ» from `sos status`; parts hide when missing, the whole
// segment hides without GPU data. A GPU the doctor flags (ok: false) shows the
// temperature in the warning color.
Row {
    id: root

    readonly property var gpu: Status.gpu
    readonly property bool hasTemp: root.gpu !== null && root.gpu.tempC !== undefined && root.gpu.tempC !== null
    readonly property bool hasVram: root.gpu !== null && !!root.gpu.vramTotalMiB

    visible: root.gpu !== null && (root.hasTemp || root.hasVram)
    spacing: 7

    BarText {
        text: Strings.gpu
        color: Theme.textFaint
    }

    BarText {
        visible: root.hasTemp
        text: root.hasTemp ? Math.round(root.gpu.tempC) + "°" : ""
        color: root.gpu && root.gpu.ok === false ? Theme.warn : Theme.textDim
    }

    BarText {
        visible: root.hasTemp && root.hasVram
        text: "·"
        color: Theme.textFaint
    }

    BarText {
        visible: root.hasVram
        text: root.hasVram ? Fmt.gbFromMib(root.gpu.vramUsedMiB || 0) + "/" + Fmt.gbFromMib(root.gpu.vramTotalMiB) + " " + Strings.gb : ""
    }
}
