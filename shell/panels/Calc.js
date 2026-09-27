.pragma library
// The launcher's calculator: type «2+2*3», «(15,5+4)/3», «200*15%», «2^10», «sqrt(2)», «√81», «pi*2»
// and the answer is the first row (Enter copies it). A small parser of its own: nothing is
// evaluated as code. Numbers take a dot or a comma; × · ÷ work too; % is percent (50% = 0,5).
// SPDX-License-Identifier: Apache-2.0

var FUNCS = {
    sqrt: Math.sqrt, abs: Math.abs, round: Math.round, floor: Math.floor, ceil: Math.ceil,
    ln: Math.log, log: function (x) { return Math.log(x) / Math.LN10; }, exp: Math.exp,
    sin: function (x) { return Math.sin(x * Math.PI / 180); },      // degrees, like a desk calculator
    cos: function (x) { return Math.cos(x * Math.PI / 180); },
    tan: function (x) { return Math.tan(x * Math.PI / 180); },
    "корень": Math.sqrt, "модуль": Math.abs
};
var CONSTS = { pi: Math.PI, "π": Math.PI, e: Math.E, "пи": Math.PI };

function tokenize(src) {
    var s = String(src).toLowerCase()
        .replace(/[×·]/g, "*").replace(/÷/g, "/").replace(/[−–—]/g, "-").replace(/\*\*/g, "^")
        .replace(/(\d)\s*[xх]\s*(?=[\d(])/g, "$1*")                        // 2x3, 2 х 3
        .replace(/(\d)[ \u00a0\u202f](?=\d{3}(?!\d))/g, "$1");               // 1 000 000
    var out = [];
    var i = 0;
    while (i < s.length) {
        var c = s[i];
        if (c === " " || c === " " || c === " " || c === "\t") {
            i++;
            continue;
        }
        var num = /^(\d+(?:[.,]\d+)?|[.,]\d+)(e[+-]?\d+)?/.exec(s.slice(i));
        if (num) {
            out.push({ t: "num", v: parseFloat(num[0].replace(",", ".")) });
            i += num[0].length;
            continue;
        }
        var word = /^[a-zа-яё]+|^π/.exec(s.slice(i));
        if (word) {
            out.push({ t: "word", v: word[0] });
            i += word[0].length;
            continue;
        }
        if ("+-*/^%()√!".indexOf(c) >= 0) {
            out.push({ t: "op", v: c });
            i++;
            continue;
        }
        return null;
    }
    return out;
}

function Parser(tokens) {
    this.tokens = tokens;
    this.pos = 0;
    this.binary = false;       // a real calculation, not just a number
}

Parser.prototype.peek = function () { return this.tokens[this.pos]; };
Parser.prototype.isOp = function (v) { var t = this.peek(); return t && t.t === "op" && t.v === v; };
Parser.prototype.take = function () { return this.tokens[this.pos++]; };

Parser.prototype.expr = function () {
    var v = this.term();
    while (this.isOp("+") || this.isOp("-")) {
        var op = this.take().v;
        this.binary = true;
        // «200 + 15%» adds 15 % of 200, as on a phone calculator
        var start = this.pos;
        var r = this.term();
        if (this.tokens[this.pos - 1] && this.tokens[this.pos - 1].t === "op" && this.tokens[this.pos - 1].v === "%"
                && this.pos - start === 2)
            r = v * r;
        v = op === "+" ? v + r : v - r;
    }
    return v;
};

Parser.prototype.term = function () {
    var v = this.power();
    for (;;) {
        if (this.isOp("*") || this.isOp("/")) {
            var op = this.take().v;
            this.binary = true;
            var r = this.power();
            v = op === "*" ? v * r : v / r;
        } else if (this.peek() && (this.peek().t === "word" || this.isOp("(") || this.isOp("√"))) {
            this.binary = true;         // «2pi», «3(4+1)»: multiplication (two numbers in a row are not: 0.53.3)
            v = v * this.power();
        } else {
            return v;
        }
    }
};

Parser.prototype.power = function () {
    var base = this.unary();
    if (this.isOp("^")) {
        this.take();
        this.binary = true;
        return Math.pow(base, this.power());       // right-associative: 2^3^2 = 2^9
    }
    return base;
};

Parser.prototype.unary = function () {
    if (this.isOp("-")) {
        this.take();
        return -this.unary();
    }
    if (this.isOp("+")) {
        this.take();
        return this.unary();
    }
    if (this.isOp("√")) {
        this.take();
        this.binary = true;
        return Math.sqrt(this.unary());
    }
    return this.postfix();
};

Parser.prototype.postfix = function () {
    var v = this.primary();
    for (;;) {
        if (this.isOp("%")) {
            this.take();
            this.binary = true;
            v = v / 100;
        } else if (this.isOp("!")) {
            this.take();
            this.binary = true;
            if (v < 0 || v > 170 || Math.floor(v) !== v)
                throw new Error("factorial");
            var f = 1;
            for (var k = 2; k <= v; k++)
                f *= k;
            v = f;
        } else {
            return v;
        }
    }
};

Parser.prototype.primary = function () {
    var t = this.take();
    if (!t)
        throw new Error("end");
    if (t.t === "num")
        return t.v;
    if (t.t === "op" && t.v === "(") {
        var v = this.expr();
        if (!this.isOp(")"))
            throw new Error("paren");
        this.take();
        return v;
    }
    if (t.t === "word") {
        if (Object.prototype.hasOwnProperty.call(CONSTS, t.v))
            return CONSTS[t.v];
        if (Object.prototype.hasOwnProperty.call(FUNCS, t.v)) {
            this.binary = true;
            return FUNCS[t.v](this.isOp("(") ? this.primary() : this.unary());
        }
    }
    throw new Error("token");
};

// → the number, or null when the text is not a calculation (a plain number, a word, «15:30»…)
function evaluate(text) {
    var src = String(text || "").trim().replace(/=\s*$/, "");
    if (src.length === 0 || src.length > 200 || !/\d|π|pi|пи/.test(src))
        return null;
    var tokens = tokenize(src);
    if (!tokens || tokens.length < 2)
        return null;
    var p = new Parser(tokens);
    try {
        var v = p.expr();
        if (p.pos !== tokens.length || !p.binary || typeof v !== "number" || !isFinite(v))
            return null;
        return v;
    } catch (e) {
        return null;
    }
}

// 0.1+0.2 → «0.3», 1/3 → «0.3333333333», 2^60 → «1152921504606846976»; a comma if the question had one
function format(v, comma) {
    var s;
    if (Math.abs(v) >= 1e21 || (v !== 0 && Math.abs(v) < 1e-9))
        s = v.toPrecision(10).replace(/\.?0+e/, "e");
    else if (Number.isInteger(v))
        s = v.toFixed(0);
    else
        s = String(parseFloat(v.toPrecision(12)));
    return comma ? s.replace(".", ",") : s;
}
