import QtQuick
import qs.core

// 6px status dot (ok / cloud; the accent only for a live signal such as a running job).
Rectangle {
    property real size: 6

    width: size
    height: size
    radius: size / 2
    color: Theme.textDim
    antialiasing: true
}
