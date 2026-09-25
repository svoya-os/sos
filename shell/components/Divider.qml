import QtQuick
import qs.core

// 1px hairline in `line`.
Rectangle {
    property bool vertical: false

    implicitWidth: vertical ? 1 : 10
    implicitHeight: vertical ? 10 : 1
    color: Theme.line
}
