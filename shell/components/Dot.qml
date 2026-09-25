import QtQuick
import qs.core

// 6px status dot (ok / cloud / accent).
Rectangle {
    property real size: 6

    width: size
    height: size
    radius: size / 2
    color: Theme.accent
    antialiasing: true
}
