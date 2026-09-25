// SPDX-License-Identifier: Apache-2.0
// Splits Jackson's streamed Markdown into blocks the panel renders natively:
//   {type: "md", text}                 paragraphs, lists, headings (Text.MarkdownText)
//   {type: "table", header, rows}      GitHub tables -> bordered mono block
//   {type: "code", lang, text}         fenced code
//   {type: "fit", capacityGb, rows}    ```svoya-fit JSON``` -> the VRAM fit table
//   {type: "actions", items}           ```svoya-actions JSON``` -> buttons
// Unterminated fences (still streaming) render as code so far.
.pragma library

function splitRow(line) {
    let s = line.trim();
    if (s.startsWith("|"))
        s = s.slice(1);
    if (s.endsWith("|"))
        s = s.slice(0, -1);
    const cells = [];
    let cur = "";
    for (let i = 0; i < s.length; i++) {
        const c = s[i];
        if (c === "\\" && i + 1 < s.length && s[i + 1] === "|") {
            cur += "|";
            i++;
        } else if (c === "|") {
            cells.push(cur.trim());
            cur = "";
        } else {
            cur += c;
        }
    }
    cells.push(cur.trim());
    return cells;
}

function isSeparator(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);
}

function stripInline(s) {
    return s.replace(/\*\*(.+?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1");
}

function parseJson(text) {
    try {
        return JSON.parse(text);
    } catch (e) {
        return null;
    }
}

function parse(src) {
    const lines = (src || "").replace(/\r\n/g, "\n").split("\n");
    const blocks = [];
    let md = [];

    function flush() {
        const t = md.join("\n").trim();
        if (t.length > 0)
            blocks.push({ type: "md", text: t });
        md = [];
    }

    let i = 0;
    while (i < lines.length) {
        const line = lines[i];
        const fence = /^\s*```\s*([\w-]*)\s*$/.exec(line);
        if (fence) {
            flush();
            const lang = fence[1] || "";
            const body = [];
            i++;
            let closed = false;
            while (i < lines.length) {
                if (/^\s*```\s*$/.test(lines[i])) {
                    closed = true;
                    i++;
                    break;
                }
                body.push(lines[i]);
                i++;
            }
            const text = body.join("\n");
            if (closed && lang === "svoya-fit") {
                const data = parseJson(text);
                const rows = Array.isArray(data) ? data : (data && Array.isArray(data.rows) ? data.rows : null);
                if (rows) {
                    blocks.push({ type: "fit", capacityGb: data && data.capacityGb ? Number(data.capacityGb) : 0, rows: rows });
                    continue;
                }
            }
            if (closed && lang === "svoya-actions") {
                const data = parseJson(text);
                if (Array.isArray(data)) {
                    blocks.push({ type: "actions", items: data });
                    continue;
                }
            }
            blocks.push({ type: "code", lang: lang, text: text });
            continue;
        }
        if (line.indexOf("|") >= 0 && i + 1 < lines.length && isSeparator(lines[i + 1])) {
            flush();
            const header = splitRow(line).map(stripInline);
            const rows = [];
            i += 2;
            while (i < lines.length && lines[i].indexOf("|") >= 0 && lines[i].trim().length > 0) {
                rows.push(splitRow(lines[i]).map(stripInline));
                i++;
            }
            blocks.push({ type: "table", header: header, rows: rows });
            continue;
        }
        md.push(line);
        i++;
    }
    flush();
    return blocks;
}
