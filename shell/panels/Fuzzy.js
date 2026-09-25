// SPDX-License-Identifier: Apache-2.0
// Small fuzzy matcher for the launcher. Case-insensitive, ё == е.
// score(query, text) -> 0 (no match) … ~1000 (exact). Ranking: exact > prefix >
// word start > substring > subsequence (consecutive runs and word starts win).
.pragma library

function norm(s) {
    return (s || "").toLowerCase().replace(/ё/g, "е");
}

function isBoundary(t, i) {
    if (i === 0)
        return true;
    const p = t[i - 1];
    return p === " " || p === "-" || p === "_" || p === "." || p === "/" || p === "(";
}

function score(query, text) {
    const q = norm(query).trim();
    const t = norm(text);
    if (q.length === 0 || t.length === 0)
        return 0;
    if (t === q)
        return 1000;
    if (t.indexOf(q) === 0)
        return 900 - Math.min(100, t.length - q.length);
    const at = t.indexOf(q);
    if (at > 0) {
        return (isBoundary(t, at) ? 800 : 600) - Math.min(100, at);
    }
    // subsequence
    let ti = 0, s = 0, run = 0;
    for (let qi = 0; qi < q.length; qi++) {
        const c = q[qi];
        if (c === " ")
            continue;
        let found = -1;
        for (let k = ti; k < t.length; k++) {
            if (t[k] === c) {
                found = k;
                break;
            }
        }
        if (found < 0)
            return 0;
        run = found === ti ? run + 1 : 1;
        s += 10 + run * 5 + (isBoundary(t, found) ? 15 : 0);
        ti = found + 1;
    }
    return Math.min(500, s - Math.min(60, t.length - q.length));
}

// Best score over several fields; weights favour the first field (the name).
function best(query, fields) {
    let top = 0;
    for (let i = 0; i < fields.length; i++) {
        const w = i === 0 ? 1 : 0.8;
        const v = score(query, fields[i]) * w;
        if (v > top)
            top = v;
    }
    return top;
}
