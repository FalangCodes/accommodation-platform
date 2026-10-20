"""Branded, paginated A4 documents rendered independently of the web page."""
from calendar import month_name
from io import BytesIO
from math import ceil
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.graphics.shapes import Drawing, Line, Circle, String, Rect

NAVY = colors.HexColor("#173752")
BLUE = colors.HexColor("#1f4e79")
TEAL = colors.HexColor("#0f766e")
GREY = colors.HexColor("#526273")
PALE = colors.HexColor("#f1f5f9")
WIDTH = A4[0] - 36 * mm


def safe(value):
    text = str(value if value is not None else "Not available")
    for old, new in [("\u2011", "-"), ("\u2013", "-"), ("\u2014", "-"), ("\u2022", "-"), ("\u00a0", " ")]:
        text = text.replace(old, new)
    return escape("".join(character for character in text if ord(character) >= 32 or character == "\n"))


def legacy_document(payload):
    return {"version": 1, "title": payload.get("entity_name") or payload["report_type"].replace("_", " ").title(),
        "audience": "Management", "period": {"label": f"{month_name[payload['period_month']]} {payload['period_year']}"},
        "generated_at": str(payload["generated_at"]),
        "summary": ["This is a legacy statistics report. Generate a new report for interpretation, evidence-based priorities and updated reporting methodology."],
        "kpis": [{"key": item["key"], "label": item["label"], "value": item["value"]} for category in payload["metrics"].values() for item in category],
        "view_history": [], "ratings": {}, "sentiment": {"counts": {}, "classified": 0, "published": 0},
        "topics": [], "actions": [], "strengths": [], "listing_priorities": [], "operations": [],
        "data_quality": ["The original figures are preserved. Legacy reports may use different inclusion rules and cannot be compared directly with new management reports."]}


def views_chart(history):
    drawing = Drawing(WIDTH, 138)
    left, bottom, width, height = 34, 30, WIDTH - 48, 95
    maximum = max(4, ceil(max((item["views"] for item in history), default=0) / 4) * 4)
    for tick in range(5):
        y = bottom + height * tick / 4
        drawing.add(Line(left, y, left + width, y, strokeColor=colors.HexColor("#dce4ec"), strokeWidth=.5))
        drawing.add(String(left - 8, y - 3, str(int(maximum * tick / 4)), textAnchor="end", fontSize=8, fillColor=GREY))
    previous = None
    for index, item in enumerate(history):
        x = left + width * index / max(1, len(history) - 1) if len(history) > 1 else left + width / 2
        y = bottom + height * item["views"] / maximum
        if previous:
            drawing.add(Line(*previous, x, y, strokeColor=BLUE, strokeWidth=2))
        drawing.add(Circle(x, y, 2.5, fillColor=BLUE, strokeColor=BLUE))
        if index in {0, len(history) - 1} or index % max(1, ceil(len(history) / 5)) == 0:
            drawing.add(String(x, 12, item["month_label"], textAnchor="middle", fontSize=7.5, fillColor=GREY))
        previous = (x, y)
    return drawing


def rating_chart(ratings):
    drawing = Drawing(WIDTH, 90)
    maximum = max(1, max(ratings.values(), default=0))
    for index, stars in enumerate(range(5, 0, -1)):
        y = 74 - index * 16
        count = ratings.get(str(stars), 0)
        drawing.add(String(0, y, f"{stars} {'star' if stars == 1 else 'stars'}", fontSize=9, fillColor=GREY))
        drawing.add(Rect(48, y-1, WIDTH-80, 9, fillColor=PALE, strokeColor=None))
        drawing.add(Rect(48, y-1, (WIDTH-80)*count/maximum, 9, fillColor=TEAL, strokeColor=None))
        drawing.add(String(WIDTH-12, y, str(count), textAnchor="end", fontSize=9, fillColor=NAVY))
    return drawing


def render_report_pdf(document, report_id=None):
    output = BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
        topMargin=34*mm, bottomMargin=22*mm, title=f"AccomFind - {document['title']}", author="AccomFind")
    styles = {
        "title": ParagraphStyle("report-title", fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=NAVY, spaceAfter=9),
        "h2": ParagraphStyle("report-section", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=NAVY, spaceBefore=16, spaceAfter=9, keepWithNext=True),
        "body": ParagraphStyle("report-body", fontName="Helvetica", fontSize=10, leading=15, textColor=NAVY, spaceAfter=7),
        "small": ParagraphStyle("report-small", fontName="Helvetica", fontSize=8.5, leading=12, textColor=GREY, spaceAfter=5),
        "cell": ParagraphStyle("report-cell", fontName="Helvetica", fontSize=9, leading=12, textColor=NAVY),
        "head": ParagraphStyle("report-table-head", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white),
    }
    para = lambda value, style="body": Paragraph(safe(value).replace("\n", "<br/>"), styles[style])
    story = []

    def section(title):
        story.append(para(title, "h2"))

    def table(headers, rows, widths):
        content = [[para(text, "head") for text in headers]] + [[para(text, "cell") for text in row] for row in rows]
        item = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT",
                     splitByRow=0 if len(rows) <= 5 else 1)
        item.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), BLUE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, PALE]),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 9),
            ("RIGHTPADDING", (0,0), (-1,-1), 9), ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LINEBELOW", (0,0), (-1,0), .5, BLUE)]))
        story.append(item)

    story += [para("MANAGEMENT REPORT", "small"), para(document["title"], "title")]
    if document.get("property_address"):
        story.append(para(document["property_address"], "small"))
    if document.get("property_profile"):
        story.append(para("Current profile: " + " | ".join(f"{item['label']}: {item['value']}" for item in document["property_profile"]), "small"))
    story += [
        para(document["period"]["label"] + (" | Month to date" if document["period"].get("partial") else " | Calendar month")),
        para(f"Prepared for: {document['audience']} | Generated: {document['generated_at'][:10]}" + (f" | Reference: AF-{report_id}" if report_id else ""), "small")]
    section("Executive assessment")
    story.extend(para(text) for text in document["summary"])
    section("Performance overview")
    rows = []
    for item in document["kpis"]:
        value = item["value"]
        shown = "Not enough data" if value is None else f"{value:,.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else str(value)
        comp = item.get("comparison")
        change = "Snapshot / cumulative"
        if comp:
            change = "No comparable rating sample" if comp["delta"] is None else f"{comp['delta']:+g}" + (" " + comp["unit"] if comp.get("unit") else f" ({comp['percent']:+g}%)" if comp["percent"] is not None else "; no percentage baseline")
        rows.append([item["label"], shown, change])
    table(["Measure", "Value", "Change vs comparison"], rows, [WIDTH*.49, WIDTH*.18, WIDTH*.33])
    story.append(Spacer(1, 5))
    story.append(para(document["period"].get("comparison_label", "Legacy reporting basis"), "small"))
    if document["view_history"]:
        story.append(KeepTogether([para("Recorded visibility over time", "h2"),
            views_chart(document["view_history"]), para("Monthly recorded page views. Missing recorded activity is shown as zero; visit dates are approximated by database flush dates.", "small")]))
    if document["ratings"]:
        section("Student experience and feedback coverage")
        sentiments = document["sentiment"]
        total = sentiments["classified"]
        rows = [[name.title(), count, f"{count / total * 100:.0f}%" if total else "Not available"] for name, count in sentiments["counts"].items()]
        table(["Overall review sentiment", "Reviews", "Share of classified reviews"], rows, [WIDTH*.49, WIDTH*.18, WIDTH*.33])
        story.append(Spacer(1, 7))
        story.append(para(f"Published reviews: {sentiments['published']}; recognised sentiment results: {total}. Rating distribution: " + "; ".join(f"{stars} {'star' if str(stars) == '1' else 'stars'}: {count}" for stars, count in document["ratings"].items()), "small"))
        story.append(rating_chart(document["ratings"]))
        coverage = document.get("reply_coverage")
        if coverage:
            story.append(para(f"Public landlord replies to published reviews: {coverage['replied']} of {coverage['published']}. Replies indicate engagement, not confirmed resolution.", "small"))
    if document["topics"]:
        section("Topics behind the feedback")
        introduction = para("Counts describe whole-review sentiment among reviews tagged with each topic, not an independent topic score. Other = neutral or unclassified sentiment.", "small")
        introduction.keepWithNext = True
        story.append(introduction)
        table(["Topic", "Mentions", "Positive", "Negative", "Other", "Priority"],
            [[r["name"], r["mentions"], r["positive"], r["negative"], r.get("neutral",0) + r.get("unclassified",0), r["priority"]] for r in document["topics"]],
            [WIDTH*.34, WIDTH*.12, WIDTH*.12, WIDTH*.12, WIDTH*.12, WIDTH*.18])
    if document["actions"]:
        section("Prioritised action plan")
        for index, action in enumerate(document["actions"], 1):
            label = action.get("priority_label", action["priority"] + " priority")
            story.append(KeepTogether([para(f"{index}. {action['title']} | {label}", "h2"),
                para("Evidence: " + action["evidence"]), para("Next step: " + action["action"]),
                para("Responsible: " + action["owner"] + " | Follow-up measure: " + action["success_measure"], "small")]))
    if document["strengths"]:
        section("Strengths to preserve")
        story.extend(para(text) for text in document["strengths"])
    if document["operations"]:
        section("Operational context - current at generation")
        table(["Measure", "Current value"], [[r["label"], r["value"]] for r in document["operations"]], [WIDTH*.72, WIDTH*.28])
    if document["listing_priorities"]:
        section("Listings for administrator follow-up")
        table(["Listing", "Period views", "Published reviews", "Follow-up"],
            [[r["title"], r["views"], f"{r['reviews']} published\n{r.get('negative', 0)} negative\n" + (f"{r['rating']}/5 rating" if r.get("rating") is not None else "No rating sample"), r["reason"]] for r in document["listing_priorities"]],
            [WIDTH*.34, WIDTH*.15, WIDTH*.17, WIDTH*.34])
        story.append(para("Up to ten listings, prioritised by publication/ownership readiness gaps, then negative-review count and recorded views. This is a follow-up queue, not a quality ranking or evidence of unsafe premises.", "small"))
    if document.get("campus_coverage"):
        section("Campus discovery coverage - current at generation")
        table(["University", "Approved linked listings", "Active verified students"],
            [[r["name"], r["approved_listings"], r["verified_students"]] for r in document["campus_coverage"]],
            [WIDTH*.5, WIDTH*.25, WIDTH*.25])
        story.append(para("Listings can serve more than one university. Counts do not measure beds, occupancy, availability or unmet housing demand.", "small"))
    section("Methodology and interpretation limits")
    story.extend(para(text, "small") for text in document["data_quality"])

    def letterhead(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.roundRect(18*mm, A4[1]-24*mm, 9*mm, 9*mm, 2*mm, stroke=0, fill=1)
        canvas.setStrokeColor(colors.white)
        canvas.setLineWidth(.9)
        canvas.rect(20.5*mm, A4[1]-22*mm, 4*mm, 5*mm, stroke=1, fill=0)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(30*mm, A4[1]-19*mm, "AccomFind")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawRightString(A4[0]-18*mm, A4[1]-19*mm, "Accommodation intelligence | accomfind.vercel.app")
        canvas.setStrokeColor(colors.HexColor("#dce4ec"))
        canvas.line(18*mm, A4[1]-27*mm, A4[0]-18*mm, A4[1]-27*mm)
        canvas.line(18*mm, 16*mm, A4[0]-18*mm, 16*mm)
        canvas.setFont("Helvetica", 8)
        reference = f"AF-{report_id}" if report_id else "Saved snapshot"
        canvas.drawString(18*mm, 11*mm, f"Confidential | {reference} | {document['period']['label']}")
        canvas.drawRightString(A4[0]-18*mm, 11*mm, f"Page {doc.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=letterhead, onLaterPages=letterhead)
    return output.getvalue()
