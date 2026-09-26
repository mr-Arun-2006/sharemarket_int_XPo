from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings


def _font_name() -> str:
    configured = getattr(settings, "report_font_path", "")
    candidates = [
        configured,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("ShareMReportFont", candidate))
                return "ShareMReportFont"
            except Exception:
                pass
    return "Helvetica"


def _clean(value: Any) -> str:
    if value is None:
        return "--"
    text = str(value).replace("–", "-").replace("—", "-").replace("−", "-")
    return text


def _para(text: Any, style: ParagraphStyle) -> Paragraph:
    safe = _clean(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    return Paragraph(safe, style)


def _kv_table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[_para(k, styles["label"]), _para(v, styles["body"])] for k, v in rows]
    table = Table(data, colWidths=[48 * mm, 124 * mm], repeatRows=0)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#d8dee9")),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f3f5f8")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    return table


def _list_table(items: list[Any], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[_para(f"- {_clean(item)}", styles["body"])] for item in items] or [[_para("--", styles["body"])]]
    table = Table(data, colWidths=[172 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.35, colors.HexColor("#d8dee9")),
        ("INNERGRID", (0,0), (-1,-1), 0.2, colors.HexColor("#edf0f4")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return table


def build_report_pdf(report: dict) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=_clean(report.get("title", "ShareM Int Xpo Report")),
        author="ShareM Int Xpo",
    )

    font = _font_name()
    styles = getSampleStyleSheet()
    styles_map = {
        "title": ParagraphStyle(
            "ReportTitle", parent=styles["Title"], fontName=font, fontSize=22,
            leading=26, alignment=TA_LEFT, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", parent=styles["Normal"], fontName=font, fontSize=9,
            leading=13, textColor=colors.HexColor("#5b6575"), spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "ReportH2", parent=styles["Heading2"], fontName=font, fontSize=13,
            leading=16, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#172033"),
        ),
        "h3": ParagraphStyle(
            "ReportH3", parent=styles["Heading3"], fontName=font, fontSize=10.5,
            leading=13, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#243047"),
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=styles["BodyText"], fontName=font, fontSize=8.8,
            leading=13, spaceAfter=4, textColor=colors.HexColor("#202734"),
        ),
        "label": ParagraphStyle(
            "ReportLabel", parent=styles["BodyText"], fontName=font, fontSize=8.5,
            leading=12, textColor=colors.HexColor("#5b6575"),
        ),
        "small": ParagraphStyle(
            "ReportSmall", parent=styles["BodyText"], fontName=font, fontSize=7.3,
            leading=10, textColor=colors.HexColor("#6a7483"),
        ),
    }

    story = [
        _para("ShareM Int Xpo", styles_map["subtitle"]),
        _para(report.get("title", "Research Report"), styles_map["title"]),
        _para(
            f"Trade date: {_clean(report.get('trade_date'))} | Generated: {_clean(report.get('generated_at'))} | Report ID: {_clean(report.get('report_id'))}",
            styles_map["subtitle"],
        ),
        Spacer(1, 4 * mm),
    ]

    summary = report.get("summary") or {}
    story.append(_para("Executive Summary", styles_map["h2"]))
    story.append(_kv_table([
        ("Overall diagnosis", summary.get("diagnosis")),
        ("Analysis type", report.get("analysis_type")),
        ("Language", report.get("language", "en")),
        ("Data status", report.get("data_status", "eod")),
    ], styles_map))

    story.append(_para("Market Findings", styles_map["h2"]))
    metrics = report.get("market_metrics") or {}
    story.append(_kv_table([
        ("NSE securities analysed", metrics.get("nse_stocks")),
        ("Positive", metrics.get("positive")),
        ("Negative", metrics.get("negative")),
        ("Unchanged", metrics.get("unchanged")),
        ("Breadth %", metrics.get("breadth_pct")),
        ("Mean change %", metrics.get("mean_change_pct")),
        ("Regime", summary.get("regime")),
    ], styles_map))

    reasons = summary.get("key_reasons") or []
    story.append(_para("Key Reasons", styles_map["h3"]))
    story.append(_list_table(reasons, styles_map))

    selected = report.get("selected_stock")
    if selected:
        story.append(_para("Selected Stock - Technical Context", styles_map["h2"]))
        latest = selected.get("latest") or {}
        technical = selected.get("technical") or {}
        story.append(_kv_table([
            ("Symbol", selected.get("symbol")),
            ("Latest trade date", latest.get("trade_date")),
            ("Close", latest.get("close")),
            ("Change %", latest.get("change_pct")),
            ("RSI 14", technical.get("rsi_14")),
            ("SMA 20", technical.get("sma_20")),
            ("EMA 20", technical.get("ema_20")),
            ("MACD", technical.get("macd")),
            ("MACD histogram", technical.get("macd_histogram")),
            ("ATR 14", technical.get("atr_14")),
            ("Annualized volatility %", technical.get("annualized_volatility_pct")),
            ("Max drawdown %", technical.get("max_drawdown_pct")),
        ], styles_map))

        story.append(_para("Fundamental / Institutional / News Sections", styles_map["h2"]))
        story.append(_list_table([
            "Fundamental financial-statement data is not included in the current EOD ingestion dataset.",
            "Institutional activity data is not included in the current EOD ingestion dataset.",
            "News and event evidence is not included in the current EOD ingestion dataset.",
        ], styles_map))

    story.append(_para("Top Gainers", styles_map["h2"]))
    gain_rows = [["Symbol", "Change %", "Close", "Volume"]]
    for item in (report.get("top_gainers") or [])[:10]:
        gain_rows.append([_clean(item.get("symbol")), _clean(item.get("change_pct")), _clean(item.get("close")), _clean(item.get("volume"))])
    gain_table = Table(gain_rows, colWidths=[45*mm, 35*mm, 40*mm, 52*mm], repeatRows=1)
    gain_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#172033")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,-1),font),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#d8dee9")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(gain_table)

    story.append(_para("Top Losers", styles_map["h2"]))
    loss_rows = [["Symbol", "Change %", "Close", "Volume"]]
    for item in (report.get("top_losers") or [])[:10]:
        loss_rows.append([_clean(item.get("symbol")), _clean(item.get("change_pct")), _clean(item.get("close")), _clean(item.get("volume"))])
    loss_table = Table(loss_rows, colWidths=[45*mm, 35*mm, 40*mm, 52*mm], repeatRows=1)
    loss_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#172033")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,-1),font),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#d8dee9")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(loss_table)

    narrative = report.get("ai_narrative")
    if narrative:
        story.append(_para("AI Explanation", styles_map["h2"]))
        story.append(_para(narrative, styles_map["body"]))

    story.append(_para("Evidence & Sources", styles_map["h2"]))
    evidence_rows = [["ID", "Type", "Evidence", "Source"]]
    for item in (report.get("evidence") or []):
        evidence_rows.append([
            _clean(item.get("id")), _clean(item.get("type")),
            _clean(item.get("label")), _clean(item.get("source")),
        ])
    ev_table = Table(evidence_rows, colWidths=[27*mm, 28*mm, 50*mm, 67*mm], repeatRows=1)
    ev_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#172033")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,-1),font),
        ("FONTSIZE",(0,0),(-1,-1),6.6),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#d8dee9")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(ev_table)

    story.append(_para("Uncertainty and Data Gaps", styles_map["h2"]))
    story.append(_list_table(report.get("uncertainty") or [], styles_map))

    story.append(Spacer(1, 4 * mm))
    story.append(_para(
        "Disclaimer: " + _clean(report.get("disclaimer", "For informational purposes only. This is not investment advice.")),
        styles_map["small"],
    ))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#6a7483"))
        canvas.drawString(18 * mm, 10 * mm, "ShareM Int Xpo - Market Intelligence")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
