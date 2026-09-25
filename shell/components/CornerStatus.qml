import QtQuick
import Quickshell
import Quickshell.Services.UPower
import qs.core

// Top-right status on the lock screen and greeter (components.css .corner):
// mono 500 11.5, +0.02em, textDim; items 16px apart, icon 15px + 7px + label.
// Lock: layout code · Wi-Fi · battery %. Greeter: Wi-Fi with its name · battery %.
Row {
    id: root

    property bool showLayout: true
    property bool showSsid: false

    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: root.battery !== null && root.battery.isLaptopBattery

    spacing: 16
    height: 15

    component Label: MText {
        anchors.verticalCenter: parent.verticalCenter
        size: 11.5
        font.weight: Font.Medium
        font.letterSpacing: 0.23
        color: Theme.textDim
    }

    Label {
        visible: root.showLayout && Hypr.layoutCode.length > 0
        text: Hypr.layoutCode
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        visible: Net.available && Net.kind !== "none"
        spacing: 7

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            glyph: Net.icon
            size: 15
        }
        Label {
            visible: root.showSsid && Net.kind === "wifi" && Net.ssid.length > 0
            text: Net.ssid
        }
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        visible: root.hasBattery
        spacing: 7

        Battery {
            anchors.verticalCenter: parent.verticalCenter
            level: root.hasBattery ? root.battery.percentage : 1
            charging: root.hasBattery && (root.battery.state === UPowerDeviceState.Charging || root.battery.state === UPowerDeviceState.PendingCharge)
        }
        Label {
            text: root.hasBattery ? Math.round(root.battery.percentage * 100) + "%" : ""
        }
    }
}
