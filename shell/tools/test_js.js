#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// Tests for the shell's JavaScript libraries that run without QML (scripts/lint.sh runs this when
// node is installed): the launcher's calculator (panels/Calc.js).
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function load(file) {
    const src = fs.readFileSync(path.join(__dirname, "..", file), "utf8").replace(/^\.pragma library\s*$/m, "");
    const ctx = {};
    vm.createContext(ctx);
    vm.runInContext(src, ctx, { filename: file });
    return ctx;
}

let failed = 0;
function expect(what, got, want) {
    if (got !== want) {
        failed++;
        console.error(`FAIL ${what}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
    }
}

const calc = load("panels/Calc.js");
const answer = q => {
    const v = calc.evaluate(q);
    return v === null ? null : calc.format(v, /\d,\d/.test(q));
};
const cases = [
    ["2+2", "4"], ["2+2*3", "8"], ["(15,5+4)/3", "6,5"], ["200*15%", "30"], ["200+15%", "230"],
    ["200-10%", "180"], ["2^10", "1024"], ["2^3^2", "512"], ["√81", "9"], ["sqrt(2)", "1.41421356237"],
    ["3(4+1)", "15"], ["2x3", "6"], ["3 × 4", "12"], ["7 ÷ 2", "3.5"], ["1 000 + 1", "1001"],
    ["0.1+0.2", "0.3"], ["5!", "120"], ["sin(30)", "0.5"], ["корень(16)", "4"], ["100 / 7 =", "14.2857142857"],
    ["2^60", "1152921504606846976"], ["50%", "0.5"],
    // not calculations: a number, a time, a date, a version, words, the launcher's secret 42
    ["42", null], ["15:30", null], ["27.09.2026", null], ["0.53.3", null], ["telegram", null],
    ["-5", null], ["1/0", null], ["(1+2", null], ["1+", null], ["2 3", null], ["", null],
];
for (const [q, want] of cases)
    expect(`calc ${JSON.stringify(q)}`, answer(q), want);

console.log(`test_js: ${cases.length} calculator cases, ${failed} failed`);
process.exit(failed ? 1 : 0);
