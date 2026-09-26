"""One page per inbox check, for GET /inbox/{id}/pdf and POST /inbox/batch-pdf.

Reuses the DejaVu fonts already bundled for the model passport (app/passport/fonts) so Cyrillic
and Uzbek Latin both render; a batch report is simply one page per item in a single document.
"""
import base64
import io
from datetime import date
from pathlib import Path

from fpdf import FPDF

FONTS = Path(__file__).resolve().parent.parent / "passport" / "fonts"
INK = (33, 37, 41)
MUTED = (108, 117, 125)
SEVERITY_COLORS = {"danger": (185, 28, 28), "warning": (146, 90, 6), "ok": (21, 101, 52), "processing": (100, 100, 100)}

T = {
    "uz": {
        "title": "Tekshiruv hisoboti",
        "file": "Fayl",
        "received_at": "Qabul qilingan",
        "status": "Holat",
        "device": "Qurilma",
        "changed_tiles": "O‘zgargan bo‘laklar",
        "detective": "Soxtalik ehtimoli (ehtimollik, isbot emas)",
        "reasons": "Sabablar",
        "reviewed": "Ko‘rib chiqilgan",
        "note": "Yakuniy qarorni shifokor qabul qiladi.",
        "footer": "MedSeal · tekshiruv hisoboti · {date}",
        "severities": {"danger": "Xavfli", "warning": "Ogohlantirish", "ok": "Yaxshi", "processing": "Jarayonda"},
        "yes": "Ha",
        "no": "Yo‘q",
        "none": "—",
    },
    "ru": {
        "title": "Отчёт о проверке",
        "file": "Файл",
        "received_at": "Получено",
        "status": "Статус",
        "device": "Устройство",
        "changed_tiles": "Изменённые блоки",
        "detective": "Вероятность подделки (вероятность, не доказательство)",
        "reasons": "Причины",
        "reviewed": "Просмотрено врачом",
        "note": "Окончательное решение принимает врач.",
        "footer": "MedSeal · отчёт о проверке · {date}",
        "severities": {"danger": "Опасно", "warning": "Предупреждение", "ok": "Хорошо", "processing": "В процессе"},
        "yes": "Да",
        "no": "Нет",
        "none": "—",
    },
    "en": {
        "title": "Verification report",
        "file": "File",
        "received_at": "Received",
        "status": "Status",
        "device": "Device",
        "changed_tiles": "Changed tiles",
        "detective": "Forgery probability (a probability, not proof)",
        "reasons": "Reasons",
        "reviewed": "Reviewed by a doctor",
        "note": "The final decision is made by a doctor.",
        "footer": "MedSeal · verification report · {date}",
        "severities": {"danger": "Danger", "warning": "Warning", "ok": "OK", "processing": "Processing"},
        "yes": "Yes",
        "no": "No",
        "none": "—",
    },
}


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


def _add_item_page(doc: _Doc, item: dict, t: dict) -> None:
    doc.add_page()
    doc.set_font("dv", "B", 16)
    doc.set_text_color(*INK)
    doc.cell(0, 9, t["title"], new_x="LMARGIN", new_y="NEXT")

    severity = item.get("severity", "processing")
    doc.set_font("dv", "B", 11)
    doc.set_text_color(*SEVERITY_COLORS.get(severity, MUTED))
    doc.cell(0, 7, t["severities"].get(severity, severity), new_x="LMARGIN", new_y="NEXT")
    doc.ln(1)

    rows = [
        (t["file"], item.get("file_name") or t["none"]),
        (t["received_at"], item.get("received_at") or t["none"]),
        (t["status"], item.get("status") or t["none"]),
        (t["device"], item.get("device") or t["none"]),
        (t["changed_tiles"], str(item.get("changed_tiles") or 0)),
        (t["reviewed"], t["yes"] if item.get("reviewed") else t["no"]),
    ]
    if item.get("detective_probability") is not None:
        rows.append((t["detective"], f"{item['detective_probability'] * 100:.0f}%"))
    reasons = item.get("reasons") or []
    if reasons:
        rows.append((t["reasons"], ", ".join(reasons)))

    for k, v in rows:
        doc.set_font("dv", "", 8.5)
        doc.set_text_color(*MUTED)
        doc.cell(52, 5.4, k)
        doc.set_text_color(*INK)
        doc.multi_cell(0, 5.4, v, align="L", new_x="LMARGIN", new_y="NEXT")

    preview = (item.get("result") or {}).get("preview_png")
    if preview:
        doc.ln(3)
        doc.image(io.BytesIO(base64.b64decode(preview)), w=110)

    doc.ln(4)
    doc.set_font("dv", "B", 8.5)
    doc.set_text_color(*INK)
    doc.cell(0, 5, t["note"])


def render(items: list[dict], lang: str = "uz") -> bytes:
    """items: inbox.detail() dicts (summary fields + full "result", incl. preview_png)."""
    t = T.get(lang, T["uz"])
    doc = _Doc(t["footer"].format(date=date.today().isoformat()))
    for item in items:
        _add_item_page(doc, item, t)
    return bytes(doc.output())
