import QtQuick
import Quickshell.Services.UPower
import qs.core
import qs.components

// Network · volume · battery (15px line icons, gap 12, textDim). A click
// opens the control center; the wheel over the group changes the volume.
Item {
    id: root

    property var screen: null
    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: root.battery !== null && root.battery.isLaptopBattery

    implicitWidth: row.implicitWidth
    implicitHeight: 15
    // Not `row.visibleChildren.length > 0`: visibleChildren counts *effective*
    // visibility, so once this item is hidden its icons never count again (latch).
    visible: Net.available || Audio.ready || root.hasBattery

    Row {
        id: row

        anchors.verticalCenter: parent.verticalCenter
        spacing: 12

        Icon {
            visible: Net.available
            glyph: Net.icon
            color: Net.kind === "none" ? Theme.textFaint : Theme.textDim
        }

        Icon {
            visible: Audio.ready
            glyph: Audio.icon
        }

        Battery {
            visible: root.hasBattery
            level: root.hasBattery ? root.battery.percentage : 1
            charging: root.hasBattery && (root.battery.state === UPowerDeviceState.Charging || root.battery.state === UPowerDeviceState.PendingCharge)
        }
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -6
        cursorShape: Qt.PointingHandCursor
        onClicked: Ui.toggle("cc", root.screen)
        onWheel: wheel => Audio.setVolume(Audio.volume + (wheel.angleDelta.y > 0 ? 0.05 : -0.05))
    }
}
