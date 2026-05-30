"""Dashboard PDF export (Phase 9) — layout legível com KPIs, barras e tabelas."""

from __future__ import annotations

import io
from datetime import datetime

from fpdf import FPDF

from app.models.dashboard import Dashboard
from app.services.metric_engine import format_metric_value

# Paleta LATAM-inspired
BRAND_BLUE = (0, 51, 102)
BRAND_RED = (232, 17, 45)
MUTED = (100, 116, 139)
BORDER = (226, 232, 240)
FILL_LIGHT = (248, 250, 252)


def _txt(value: object) -> str:
    """fpdf Helvetica = latin-1; substitui caracteres fora do range."""
    if value is None:
        return ""
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _fmt_value(value: float | None, *, output_format: str = "number", decimals: int = 2) -> str:
    return _txt(format_metric_value(value, output_format=output_format, decimals=decimals))


class DashboardPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, _txt(f"LATAM Analytics Platform  |  Page {self.page_no()}"), align="C")


def _ensure_space(pdf: FPDF, height: float) -> None:
    if pdf.get_y() + height > pdf.page_break_trigger:
        pdf.add_page()


def _section_title(pdf: FPDF, title: str, widget_type: str) -> None:
    _ensure_space(pdf, 16)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, _txt(title), ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, _txt(widget_type.replace("_", " ").title()), ln=True)
    pdf.ln(2)


def _draw_kpi(pdf: FPDF, kpi: dict) -> None:
    _ensure_space(pdf, 28)
    x0 = pdf.l_margin
    w = pdf.w - pdf.l_margin - pdf.r_margin
    y0 = pdf.get_y()
    pdf.set_fill_color(*FILL_LIGHT)
    pdf.set_draw_color(*BORDER)
    pdf.rect(x0, y0, w, 24, style="FD")
    pdf.set_xy(x0 + 6, y0 + 4)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(w - 12, 5, _txt(kpi.get("label", "KPI")), ln=True)
    pdf.set_x(x0 + 6)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BRAND_BLUE)
    formatted = kpi.get("formatted")
    if not formatted and kpi.get("value") is not None:
        formatted = _fmt_value(
            kpi.get("value"),
            output_format=kpi.get("output_format", "number"),
            decimals=int(kpi.get("decimals", 2)),
        )
    pdf.cell(w - 12, 12, _txt(formatted or "—"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + 28)


def _chart_values(chart: dict) -> tuple[list[str], list[float | None], str, int]:
    categories = [str(c) for c in chart.get("categories") or []]
    series = chart.get("series") or []
    values: list[float | None] = []
    if series:
        values = list(series[0].get("values") or [])
    output_format = str(chart.get("output_format") or "number")
    decimals = int(chart.get("decimals") or 2)
    return categories, values, output_format, decimals


def _draw_horizontal_bars(pdf: FPDF, chart: dict) -> None:
    categories, values, output_format, decimals = _chart_values(chart)
    if not categories or not values:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 6, "Sem dados para exibir.", ln=True)
        return

    label_w = 42
    value_w = 36
    bar_area = pdf.w - pdf.l_margin - pdf.r_margin - label_w - value_w - 4
    bar_h = 7
    max_val = max((v for v in values if v is not None), default=0) or 1

    for cat, val in zip(categories, values):
        _ensure_space(pdf, bar_h + 2)
        y = pdf.get_y()
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(label_w, bar_h, _txt(cat)[:22], align="L")

        bx = pdf.l_margin + label_w
        pdf.set_draw_color(*BORDER)
        pdf.set_fill_color(241, 245, 249)
        pdf.rect(bx, y + 1.5, bar_area, bar_h - 3, style="FD")

        if val is not None and val > 0:
            bw = max(1.0, (float(val) / max_val) * bar_area)
            pdf.set_fill_color(*BRAND_BLUE)
            pdf.rect(bx, y + 1.5, bw, bar_h - 3, style="F")

        pdf.set_xy(bx + bar_area + 2, y)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*BRAND_BLUE)
        pdf.cell(value_w, bar_h, _fmt_value(val, output_format=output_format, decimals=decimals), align="R", ln=True)

    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _draw_distribution_table(pdf: FPDF, chart: dict) -> None:
    """Pie / donut — tabela categoria + valor + % do total."""
    categories, values, output_format, decimals = _chart_values(chart)
    if not categories or not values:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 6, "Sem dados para exibir.", ln=True)
        return

    numeric = [float(v) for v in values if v is not None]
    total = sum(numeric) or 1.0
    col_w = (pdf.w - pdf.l_margin - pdf.r_margin) / 3

    _ensure_space(pdf, 10)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*BRAND_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_w, 7, "Categoria", border=1, fill=True)
    pdf.cell(col_w, 7, "Valor", border=1, fill=True)
    pdf.cell(col_w, 7, "% Total", border=1, fill=True, ln=True)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(51, 65, 85)
    for i, (cat, val) in enumerate(zip(categories, values)):
        _ensure_space(pdf, 8)
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*FILL_LIGHT)
        else:
            pdf.set_fill_color(255, 255, 255)
        pct = (float(val) / total * 100) if val is not None else 0
        pdf.cell(col_w, 6, _txt(cat)[:28], border=1, fill=fill)
        pdf.cell(col_w, 6, _fmt_value(val, output_format=output_format, decimals=decimals), border=1, fill=fill)
        pdf.cell(col_w, 6, f"{pct:.1f}%", border=1, fill=fill, ln=True)

    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _draw_table(pdf: FPDF, table: dict) -> None:
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    if not columns:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 6, "Tabela vazia.", ln=True)
        return

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable / min(len(columns), 6)
    shown_cols = columns[:6]

    _ensure_space(pdf, 10)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(*BRAND_BLUE)
    pdf.set_text_color(255, 255, 255)
    for col in shown_cols:
        pdf.cell(col_w, 6, _txt(str(col))[:18], border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(51, 65, 85)
    for i, row in enumerate(rows[:15]):
        _ensure_space(pdf, 7)
        fill = i % 2 == 0
        pdf.set_fill_color(*FILL_LIGHT if fill else (255, 255, 255))
        for col in shown_cols:
            val = row.get(col, "")
            pdf.cell(col_w, 6, _txt(str(val))[:20], border=1, fill=fill)
        pdf.ln()

    if len(rows) > 15:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, _txt(f"... +{len(rows) - 15} linhas (limitado no PDF)"), ln=True)

    total = table.get("total_rows")
    if total is not None:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, _txt(f"Total no dataset: {total} linhas"), ln=True)

    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _draw_text(pdf: FPDF, text: str) -> None:
    _ensure_space(pdf, 12)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(0, 5, _txt(text))
    pdf.ln(2)


def _render_widget(pdf: FPDF, item: dict) -> None:
    title = str(item.get("title") or "Widget")
    wtype = str(item.get("widget_type") or "")
    _section_title(pdf, title, wtype)

    if item.get("notes"):
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*BRAND_RED)
        pdf.multi_cell(0, 4, _txt(str(item["notes"])[:300]))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        return

    if item.get("kpi"):
        _draw_kpi(pdf, item["kpi"])
        return

    if item.get("text"):
        _draw_text(pdf, str(item["text"]))
        return

    if item.get("table"):
        _draw_table(pdf, item["table"])
        return

    chart = item.get("chart")
    if chart:
        if wtype in {"pie_chart", "donut_chart"}:
            _draw_distribution_table(pdf, chart)
        else:
            _draw_horizontal_bars(pdf, chart)
        return

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "Widget sem conteudo renderizavel.", ln=True)


def build_dashboard_pdf(dashboard: Dashboard, rendered: list[dict]) -> bytes:
    pdf = DashboardPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    # Cabecalho
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BRAND_BLUE)
    pdf.cell(0, 10, _txt(dashboard.name[:80]), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    meta = f"Workspace: {dashboard.workspace}  |  Status: {dashboard.status}"
    if dashboard.business_area:
        meta += f"  |  Area: {dashboard.business_area}"
    pdf.cell(0, 6, _txt(meta), ln=True)
    pdf.cell(0, 6, _txt(f"Exportado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"), ln=True)
    if dashboard.description:
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _txt(dashboard.description[:400]))

    pdf.ln(4)
    pdf.set_draw_color(*BRAND_RED)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    for item in rendered:
        _render_widget(pdf, item)
        pdf.ln(4)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
