import QtQuick
import qs.core
import qs.components

// Running job from `sos status`: dot + label + 34×4 meter + percent
// («● обучение ▬▬▬ 62%»); hidden without jobs.
Row {
    id: root

    readonly property var job: Status.job
    readonly property real progress: root.job && root.job.progress !== undefined && root.job.progress !== null ? Number(root.job.progress) : -1

    visible: root.job !== null
    spacing: 7

    Dot {
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.accent
    }

    BarText {
        anchors.verticalCenter: parent.verticalCenter
        text: root.job ? (root.job.label || root.job.id || "") : ""
    }

    Meter {
        anchors.verticalCenter: parent.verticalCenter
        visible: root.progress >= 0
        value: Math.max(0, root.progress)
    }

    BarText {
        anchors.verticalCenter: parent.verticalCenter
        visible: root.progress >= 0
        text: Fmt.pct(root.progress)
    }
}
