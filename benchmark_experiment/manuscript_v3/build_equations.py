"""Optional regeneration of editable OMML using Microsoft's installed transform.

The generated equations.omml.json is checked in; rebuilding the manuscript does
not require Office or this optional conversion step.
"""

import json
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
TRANSFORM = Path("C:/Program Files/Microsoft Office/root/Office16/MML2OMML.XSL")
transform = etree.XSLT(etree.parse(str(TRANSFORM)))


def mi(t):
    return f"<mi>{t}</mi>"


def mo(t):
    return f"<mo>{t}</mo>"


def mn(t):
    return f"<mn>{t}</mn>"


def row(*xs):
    return "<mrow>" + "".join(xs) + "</mrow>"


def sub(a, b):
    return "<msub>" + a + b + "</msub>"


def sup(a, b):
    return "<msup>" + a + b + "</msup>"


def fence(x, left="[", right="]"):
    return f'<mfenced open="{left}" close="{right}">' + row(x) + "</mfenced>"


def q(p):
    return "<msubsup>" + mi("q") + mn(p) + mi("B") + "</msubsup>"


def f(t):
    return row(mi(t), fence(mi("x"), "(", ")"))


def interval_name(t):
    return sub(mi("I"), f"<mtext>{t}</mtext>")


def tr(center=False):
    return row(sub(mi("T"), mi("c")) if center else mi("T"), fence(mi("x"), "(", ")"))


hat = '<mover accent="true">' + mi("H") + mo("^") + "</mover>"
model_center = row(tr(True), mo("+"), sub(hat, mi("ML")))
gamma_terms = []
for k in [row(mi("k"), mo("+"), mn("1")), mi("k"), row(mi("k"), mo("−"), mn("1"))]:
    gamma_terms.append(sup(fence(k, "|", "|"), row(mn("2"), mi("H"))))
formulae = [
    [
        row(
            mi("γ"),
            fence(mi("k"), "(", ")"),
            mo("="),
            "<mfrac>" + mn("1") + mn("2") + "</mfrac>",
            fence(
                row(gamma_terms[0], mo("−"), mn("2"), gamma_terms[1], mo("+"), gamma_terms[2]),
                "(",
                ")",
            ),
        )
    ],
    [
        row(interval_name("percentile"), mo("="), fence(row(q("0.025"), mo(","), q("0.975")))),
        row(
            interval_name("basic"),
            mo("="),
            fence(
                row(mn("2"), tr(), mo("−"), q("0.975"), mo(","), mn("2"), tr(), mo("−"), q("0.025"))
            ),
        ),
    ],
    [
        row(
            interval_name("fGn"),
            mo("="),
            fence(
                row(model_center, mo("−"), q("0.975"), mo(","), model_center, mo("−"), q("0.025"))
            ),
        )
    ],
    [
        row(
            mi("ΔMAE"),
            mo("="),
            sub(mi("mean"), mi("r")),
            fence(
                row(
                    fence(
                        row(
                            "<msubsup>" + mi("T") + mi("r") + mi("c") + "</msubsup>",
                            mo("−"),
                            sub(mi("H"), mi("r")),
                        ),
                        "|",
                        "|",
                    ),
                    mo("−"),
                    fence(row(sub(mi("T"), mi("r")), mo("−"), sub(mi("H"), mi("r"))), "|", "|"),
                )
            ),
        ),
        row(
            sub(mi("D"), mi("A")),
            mo("="),
            sub(mi("mean"), mi("r")),
            fence(
                row(
                    "<msubsup>" + mi("T") + mi("r") + mi("c") + "</msubsup>",
                    mo("−"),
                    sub(mi("T"), mi("r")),
                ),
                "|",
                "|",
            ),
        ),
    ],
]
out = []
for group in formulae:
    out.append([])
    for formula in group:
        source = etree.fromstring(
            ('<math xmlns="http://www.w3.org/1998/Math/MathML">' + formula + "</math>").encode()
        )
        converted = transform(source)
        out[-1].append(etree.tostring(converted, encoding="unicode"))
(HERE / "equations.omml.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
)
print("Generated six native equations in four groups")
