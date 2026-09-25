pragma Singleton

// Jackson's look and name (DESIGN.md §13): ~/.config/svoya/avatar.json, shared with jacksond
// (jackson/jackson/avatar.py — same keys, defaults and validation). The file may be sparse;
// missing keys follow the character's defaults, invalid values fall back to them, and keys this
// shell does not know are kept on every write (a newer Jackson may have added them).
// Writes are atomic (FileView writes a temp file and renames it); jacksond notices the change.
//
// Also loads the sprite data (assets/jackson/imp.json, cat.json; format sos-jackson/1) once and
// says which accent the mascot wears: the system accent, or the one previewed on hover.

import QtQuick
import Quickshell
import Quickshell.Io
import "Color.js" as Color

Singleton {
    id: root

    // The greeter runs as its own user: it shows the copy `sos theme … --system` exported for the login
    // screen (/etc/svoya/avatar.json, cli/svoya_cli/theme/avatar_export.py) and never writes.
    readonly property bool readOnly: Theme.systemTheme
    readonly property string path: root.readOnly ? "/etc/svoya/avatar.json" : Settings.configDir + "/avatar.json"
    readonly property string defaultName: "Джексон"

    readonly property var characters: ["imp", "cat"]
    readonly property var skins: ({
            imp: ["ember", "wine", "plum", "graphite", "mint"],
            cat: ["blue", "ginger", "black", "snow", "siamese"]
        })
    readonly property var styles: ["hoodie", "jacket", "tee"]
    readonly property var glassesKinds: ["none", "shades", "round"]
    readonly property var defaultsFor: ({
            imp: { character: "imp", skin: "ember", outfit: "accent", style: "hoodie", headphones: true, glasses: "none", hood: true, name: "Джексон" },
            cat: { character: "cat", skin: "blue", outfit: "accent", style: "jacket", headphones: true, glasses: "shades", hood: true, name: "Джексон" }
        })

    // what the file says (sparse), and the complete look
    property var stored: ({})
    readonly property var look: root.resolve(root.stored)
    readonly property string character: root.look.character
    readonly property string name: root.look.name === root.defaultName && !Strings.ru ? "Jackson" : root.look.name
    // The greeter only: how Jackson's fixed lines sound — «kent» (default persona) or «plain» (another
    // persona, humor 0). `sos theme … --system` exports it with the look (avatar_export.user_voice).
    readonly property string voice: root.stored && root.stored.voice === "plain" ? "plain" : "kent"

    // sprite data for a character (null until loaded / when the file is missing)
    readonly property var impData: root.parseData(impFile.text())
    readonly property var catData: root.parseData(catFile.text())
    readonly property var data: root.dataFor(root.character)

    function dataFor(character) {
        return character === "cat" ? root.catData : root.impData;
    }

    // The accent the outfit/detail follow: an id the sprite data knows, else "#rrggbb".
    readonly property string mode: Theme.isDark ? "dark" : "light"
    readonly property string spriteAccent: {
        const shown = Theme.shownAccent.length > 0 ? Theme.shownAccent : Theme.accentChoice;
        const d = root.data;
        if (d && d.accents && d.accents[shown])
            return shown;
        const hex = Color.normalize(String(Theme.targetAccent));
        return hex.length > 0 ? hex : "#ffb547";
    }

    // skin colors when the sprite data is not there (the same values as assets/jackson/*.json)
    readonly property var skinFallback: ({
            ember: "#d9553b", wine: "#a8384d", plum: "#8c55a3", graphite: "#747b89", mint: "#5cbf98",
            blue: "#8f9bb1", ginger: "#e08b3e", black: "#434753", snow: "#eef0f5", siamese: "#efe3cc"
        })

    function skinColor(skin, character) {
        const d = root.dataFor(character || root.character);
        if (d && d.skins && d.skins[skin] && d.skins[skin].colors && d.skins[skin].colors.skin)
            return d.skins[skin].colors.skin;
        return root.skinFallback[skin] || "#888888";
    }

    function skinName(skin, character) {
        const d = root.dataFor(character || root.character);
        const n = d && d.skins && d.skins[skin] ? d.skins[skin].name : null;
        if (n && (n.ru || n.en))
            return (Strings.ru ? n.ru : n.en) || n.en || skin;
        return Strings.skinNames[skin] || skin;
    }

    // the outfit's main color for "accent", an accent id or "#hex" (DESIGN §13: OKLCH shades)
    function outfitColor(choice, character) {
        const d = root.dataFor(character || root.character);
        const c = choice === "accent" ? root.spriteAccent : choice;
        if (d && d.accents && d.accents[c] && d.accents[c][root.mode])
            return d.accents[c][root.mode].outfit;
        const a = Color.accentById(c);
        const hex = a ? (root.mode === "light" ? a.light : a.dark) : Color.normalize(c);
        return hex.length > 0 ? Color.outfitFor(hex, root.mode).outfit : "#3a3d44";
    }

    function parseData(text) {
        if (!text || text.length === 0)
            return null;
        try {
            const d = JSON.parse(text);
            return d && d.format === "sos-jackson/1" && d.states && d.layers ? d : null;
        } catch (e) {
            console.warn("svoya: avatar: bad sprite data:", e);
            return null;
        }
    }

    function validName(n) {
        return typeof n === "string" && n.trim().length > 0 && n.trim().length <= 24 && !/[\u0000-\u001f<>]/.test(n) && /^[^\s.'’-]/.test(n.trim());
    }

    function isHex(v) {
        return typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v);
    }

    // sparse file content -> complete look (jackson/avatar.py resolve())
    function resolve(s) {
        const src = s && typeof s === "object" ? s : {};
        const character = root.characters.indexOf(src.character) >= 0 ? src.character : "imp";
        const out = Object.assign({}, root.defaultsFor[character]);
        if (root.skins[character].indexOf(src.skin) >= 0)
            out.skin = src.skin;
        const outfit = src.outfit;
        if (typeof outfit === "string" && (outfit === "accent" || Color.accentById(outfit) || root.isHex(outfit)))
            out.outfit = outfit.toLowerCase();
        if (root.styles.indexOf(src.style) >= 0)
            out.style = src.style;
        if (typeof src.headphones === "boolean")
            out.headphones = src.headphones;
        if (root.glassesKinds.indexOf(src.glasses) >= 0)
            out.glasses = src.glasses;
        if (typeof src.hood === "boolean")
            out.hood = src.hood;
        if (root.validName(src.name))
            out.name = src.name.trim();
        return out;
    }

    // ---- writing -------------------------------------------------------------------------------------
    function write(obj) {
        if (root.readOnly)
            return;
        root.stored = obj;
        file.setText(JSON.stringify(obj, null, 2) + "\n");
        // the login screen shows this Jackson too when the look goes there (no-op otherwise)
        Theme.queueSystemSync();
    }

    // One change; returns false when the value is not valid for the key.
    function set(key, value) {
        const next = Object.assign({}, root.stored);
        if (key === "name") {
            if (!root.validName(value))
                return false;
            value = value.trim();
        }
        if (key === "character" && root.characters.indexOf(value) < 0)
            return false;
        next[key] = value;
        // a skin that belongs to the other character would be ignored anyway: drop it
        if (key === "character" && next.skin !== undefined && root.skins[value].indexOf(next.skin) < 0)
            delete next.skin;
        root.write(next);
        return true;
    }

    // back to the defaults (unknown keys stay, like `j avatar reset`)
    function reset() {
        const keep = {};
        const known = ["character", "skin", "outfit", "style", "headphones", "glasses", "hood", "name"];
        for (const k in root.stored) {
            if (known.indexOf(k) < 0)
                keep[k] = root.stored[k];
        }
        root.write(keep);
    }

    FileView {
        id: file

        path: root.path
        watchChanges: true
        atomicWrites: true // temp file + rename: jacksond never reads half a file
        printErrors: false // no avatar.json = all defaults
        onFileChanged: reload()
        onLoaded: {
            try {
                const d = JSON.parse(file.text());
                root.stored = d && typeof d === "object" && !Array.isArray(d) ? d : ({});
            } catch (e) {
                root.stored = ({});
            }
        }
        onLoadFailed: root.stored = ({})
    }

    FileView {
        id: impFile

        path: Theme.assetPath("jackson/imp.json")
        printErrors: false
    }

    FileView {
        id: catFile

        path: Theme.assetPath("jackson/cat.json")
        printErrors: false
    }
}
