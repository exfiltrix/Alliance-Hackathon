"""One-page A4 passport PDF (fpdf2 + bundled DejaVu Sans: Cyrillic and Uzbek Latin)."""
import base64
import io
from pathlib import Path

from fpdf import FPDF

from app.passport.i18n import T

FONTS = Path(__file__).with_name("fonts")
INK = (33, 37, 41)
MUTED = (108, 117, 125)
LINE = (222, 226, 230)
VERDICT_COLORS = {  # background, text
    "allowed": ((220, 245, 228), (21, 101, 52)),
    "allowed_with_conditions": ((255, 243, 205), (133, 77, 14)),
    "not_allowed": ((252, 226, 226), (153, 27, 27)),
}
BAR = (220, 53, 69)
W = 180  # printable width (A4 210 mm - 2 x 15 mm)
LEFT_W = 100  # robustness text/table column; the before/after example sits to the right


class _Doc(FPDF):
    def __init__(self, footer_text: str):
        super().__init__(format="A4")
        self.footer_text = footer_text
        self.add_font("dv", "", FONTS / "DejaVuSans.ttf")
        self.add_font("dv", "B", FONTS / "DejaVuSans-Bold.ttf")
        self.set_margins(15, 12, 15)
        self.set_auto_page_break(True, margin=14)

    def footer(self):
        self.set_y(-11)
        self.set_font("dv", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 4, self.footer_text, align="C")

    def text(self, size: float, value: str, bold=False, color=INK, h=None, w=0):
        self.set_font("dv", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(w, h or size * 0.5, value, align="L", new_x="LMARGIN", new_y="NEXT")

    def section(self, title: str):
        self.ln(2.5)
        self.text(10.5, title, bold=True)
        self.set_draw_color(*LINE)
        self.line(15, self.get_y() + 0.5, 15 + W, self.get_y() + 0.5)
        self.ln(1.5)

    def rows(self, pairs: list[tuple[str, str]], key_w=70):
        for k, v in pairs:
            self.set_font("dv", "", 8.5)
            self.set_text_color(*MUTED)
            self.cell(key_w, 4.6, k)
            self.set_text_color(*INK)
            self.multi_cell(W - key_w, 4.6, v, align="L", new_x="LMARGIN", new_y="NEXT")


def _pct(v) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _png(b64: str) -> io.BytesIO:
    return io.BytesIO(base64.b64decode(b64))


def render(p: dict, lang: str = "uz") -> bytes:
    t = T[lang]
    date = p["created_at"][:10]
    doc = _Doc(t["footer"].format(id=p["id"], date=date))
    doc.add_page()
    pathology = t["pathologies"].get(p["robustness"]["pathology"], p["robustness"]["pathology"])

    # header
    doc.text(18, t["title"], bold=True, h=8)
    doc.text(9, t["subtitle"] + " · " + t["passport_no"].format(id=p["id"]), color=MUTED)
    doc.ln(1)
    doc.rows([
        (t["issued"], date),
        (t["organisation"], p["organisation"] or "—"),
    ], key_w=55)

    # verdict first: it is what the reader is looking for
    bg, fg = VERDICT_COLORS[p["verdict"]]
    doc.ln(2)
    y0 = doc.get_y()
    conds = [t["condition_texts"][c] for c in p["conditions"]]
    box_h = 12 + 4.6 * len(conds) + (4 if conds else 0)
    doc.set_fill_color(*bg)
    doc.rect(15, y0, W, box_h, style="F")
    doc.set_xy(19, y0 + 2.5)
    doc.set_font("dv", "", 8)
    doc.set_text_color(*fg)
    doc.cell(0, 4, t["verdict"].upper(), new_x="LMARGIN", new_y="NEXT")
    doc.set_x(19)
    doc.set_font("dv", "B", 15)
    doc.cell(0, 7, t["verdicts"][p["verdict"]], new_x="LMARGIN", new_y="NEXT")
    doc.set_font("dv", "", 8.5)
    for c in conds:
        doc.set_x(19)
        doc.multi_cell(W - 8, 4.6, "•  " + c, align="L", new_x="LMARGIN", new_y="NEXT")
    doc.set_y(y0 + box_h)

    # model
    m = p["model"]
    doc.section(t["model"])
    doc.rows([(t["name"], m["name"]), (t["version"], m["version"]), (t["source"], m["source"]),
              (t["intended_use"], m["intended_use"])])

    # robustness
    r = p["robustness"]
    doc.section(t["robustness"])
    y_top = doc.get_y()
    doc.set_font("dv", "B", 22)
    doc.set_text_color(*INK)
    doc.cell(30, 10, f"{r['score']:.1f}")
    doc.set_font("dv", "", 10)
    doc.set_text_color(*MUTED)
    doc.cell(0, 12, f"/ 10   {t['score']}", new_x="LMARGIN", new_y="NEXT")
    ex = r.get("example")
    text_w = LEFT_W if ex else 0
    doc.text(8, t["formula"], color=MUTED, w=text_w)
    doc.text(8, t["crash_test"].format(n=r["n_images"], method=r["method"].upper(), pathology=pathology,
                                       date=r["tested_at"][:10]), color=MUTED, w=text_w)
    doc.ln(1.5)

    # flip-rate table with bars (left) + before/after example (right)
    col = [30, 50, 20]
    doc.set_font("dv", "B", 8)
    doc.set_text_color(*INK)
    for w, h in zip(col, (t["eps"], t["flipped"], t["psnr"])):
        doc.cell(w, 5, h)
    doc.ln(5)
    doc.set_font("dv", "", 8.5)
    for eps, rate in r["flip_rate"].items():
        y = doc.get_y()
        doc.cell(col[0], 5.5, eps)
        doc.set_fill_color(*LINE)
        doc.rect(15 + col[0], y + 1.2, 34, 3.2, style="F")
        doc.set_fill_color(*BAR)
        if rate > 0:
            doc.rect(15 + col[0], y + 1.2, 34 * rate, 3.2, style="F")
        doc.set_x(15 + col[0] + 36)
        doc.cell(col[1] - 36, 5.5, _pct(rate))
        doc.cell(col[2], 5.5, f"{r['psnr'].get(eps, 0):.1f}")
        doc.ln(5.5)
    doc.text(7.5, t["psnr_note"], color=MUTED, w=text_w)
    y_after_table = doc.get_y()

    if ex:
        x0, size = 118, 32
        doc.set_xy(x0, y_top)
        doc.set_font("dv", "B", 8)
        doc.set_text_color(*INK)
        doc.cell(2 * size + 4, 4, t["example"].format(eps=f"{ex['eps']:g}"))
        for i, (key, label) in enumerate((("before", t["before"]), ("after", t["after"]))):
            x = x0 + i * (size + 4)
            doc.image(_png(ex[f"{key}_png"]), x=x, y=y_top + 5, w=size, h=size)
            doc.set_xy(x, y_top + 6 + size)
            doc.set_font("dv", "B" if key == "after" else "", 7.5)
            doc.set_text_color(*(BAR if key == "after" else INK))
            doc.cell(size, 4, label.format(pathology=pathology, score=_pct(ex[f"{key}_score"])), align="C")
        doc.set_y(max(y_after_table, y_top + size + 12))

    # shield
    s = p["shield"]
    doc.section(t["shield"])
    status = t["shield_ok"] if s["compatible"] else (t["shield_weak"] if s["available"] else t["shield_missing"])
    rows = [(t["shield_status"], status)]
    if s["available"]:
        rows += [
            (t["shield_method"], s["method"]),
            (t["shield_threshold"], f"{s['threshold']:g}"),
            (t["shield_fpr"], f"{s['false_positive_rate'] * 100:.1f}%"),
            (t["shield_pgd"], _pct(s["detection_pgd_eps1"])),
            (t["shield_fgsm"], _pct(s["detection_fgsm_eps1"])),
        ]
    doc.rows(rows)

    # pipeline
    pl = p["pipeline"]
    doc.section(t["pipeline"])
    doc.rows([
        (t["devices_active"], str(pl["devices_active"])),
        (t["seals"], str(pl["seals"])),
        (t["verifications"], str(pl["verifications"])),
        (t["tampered_or_forged"], str(pl["tampered_or_forged"])),
        (t["ledger"], t["ledger_ok"] if pl["ledger_ok"] else t["ledger_broken"]),
    ])

    rules = p["rules"]
    doc.ln(3)
    doc.text(7.5, t["rules"].format(allow=f"{rules['allow_score']:g}", det=f"{rules['shield_min_detection'] * 100:.0f}",
                                    fpr=f"{rules['shield_max_false_alarms'] * 100:.0f}"), color=MUTED)
    doc.ln(1)
    doc.text(8.5, t["note"], bold=True)
    return bytes(doc.output())
