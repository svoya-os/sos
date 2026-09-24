pragma Singleton

// Locale-aware number and time formatting (DESIGN.md §8: Russian uses a
// decimal comma and thin spaces in thousands: «11,2 ГБ», «48 213»).

import QtQuick
import Quickshell

Singleton {
    id: root

    readonly property string decimal: Strings.ru ? "," : "."
    readonly property string group: Strings.ru ? "\u2009" : ","

    function integer(n) {
        const v = Math.round(Number(n) || 0);
        const s = Math.abs(v).toString();
        let out = "";
        for (let i = 0; i < s.length; i++) {
            if (i > 0 && (s.length - i) % 3 === 0)
                out += root.group;
            out += s[i];
        }
        return (v < 0 ? "−" : "") + out;
    }

    // Fixed decimals with the locale separator; "11,2".
    function num(v, decimals) {
        const n = Number(v) || 0;
        const d = decimals === undefined ? 1 : decimals;
        const fixed = Math.abs(n).toFixed(d);
        const parts = fixed.split(".");
        const whole = root.integer(Number(parts[0]));
        return (n < 0 ? "−" : "") + whole + (parts.length > 1 ? root.decimal + parts[1] : "");
    }

    // One decimal unless the value is (almost) whole: 23.99 -> "24", 11.2 -> "11,2".
    function smart(v) {
        const n = Number(v) || 0;
        return Math.abs(n - Math.round(n)) < 0.05 ? root.integer(Math.round(n)) : root.num(n, 1);
    }

    // Euro amounts: 0 -> "0", 0.004 -> "<0,01", 0.12 -> "0,12".
    function money(v) {
        const n = Number(v) || 0;
        if (n === 0)
            return "0";
        if (n < 0.01)
            return "<" + root.num(0.01, 2);
        return root.num(n, 2);
    }

    function gbFromMib(mib) {
        return root.smart((Number(mib) || 0) / 1024);
    }

    function pct(fraction) {
        return Math.round((Number(fraction) || 0) * 100) + "%";
    }

    function clock(date) {
        return Qt.formatTime(date, "HH:mm");
    }

    function duration(seconds) {
        const s = Math.max(0, Math.round(Number(seconds) || 0));
        if (s < 60)
            return s + (Strings.ru ? " с" : " s");
        const m = Math.round(s / 60);
        if (m < 60)
            return m + (Strings.ru ? " мин" : " min");
        const h = Math.floor(m / 60);
        return h + (Strings.ru ? " ч " : " h ") + (m % 60) + (Strings.ru ? " мин" : " min");
    }

    // Relative time for notifications: "сейчас", "5 мин назад", "18:42".
    function ago(date, now) {
        if (!date)
            return "";
        const diff = Math.floor((now.getTime() - date.getTime()) / 60000);
        if (diff < 1)
            return Strings.now;
        if (diff < 60)
            return Strings.minutesAgo(diff);
        return root.clock(date);
    }

    function bytes(n) {
        const v = Number(n) || 0;
        const units = Strings.ru ? ["Б", "КБ", "МБ", "ГБ", "ТБ"] : ["B", "KB", "MB", "GB", "TB"];
        let i = 0;
        let x = v;
        while (x >= 1024 && i < units.length - 1) {
            x /= 1024;
            i++;
        }
        return (i === 0 ? root.integer(x) : root.smart(x)) + " " + units[i];
    }
}
