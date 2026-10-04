"""Build a readable enquiry with escaped HTML and a plain-text alternative."""
from html import escape
from unicodedata import category
from urllib.parse import quote, urlsplit


def enquiry_subject(title: str) -> str:
    # Listing names may contain line breaks or control characters; headers may not.
    clean = "".join(" " if char in "\r\n\t" else char for char in title
                    if not category(char).startswith("C") or char in "\r\n\t")
    clean = " ".join(clean.split()) or "Student accommodation"
    prefix = "Accommodation enquiry: "
    limit = 100 - len(prefix)
    if len(clean) > limit:
        clean = clean[:limit - 1].rstrip() + "…"
    return prefix + clean


def build_enquiry_email(title: str, listing_url: str, name: str, student_email: str, message: str):
    parsed_url = urlsplit(listing_url)
    if parsed_url.scheme not in ("https", "http") or not parsed_url.netloc:
        raise ValueError("The listing link must be an HTTP or HTTPS URL")
    plain = (
        f"Accommodation enquiry\n{title}\n\n{message}\n\n"
        f"Sent from this student account\n{name}\nVerified email: {student_email}\n\n"
        f"View listing: {listing_url}\n\n"
        "Reply to this email to contact the student directly.\n"
    )
    title_html, name_html, email_html = escape(title), escape(name), escape(student_email)
    message_html = escape(message.replace("\r\n", "\n").replace("\r", "\n")).replace("\n", "<br>\n")
    url_html = escape(listing_url, quote=True)
    email_link = escape("mailto:" + quote(student_email, safe="@."), quote=True)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f4f7fb;color:#1e293b;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f4f7fb;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:16px;">
<tr><td style="background-color:#112a46;padding:24px 32px;border-radius:16px 16px 0 0;">
<span style="font-size:22px;font-weight:bold;color:#ffffff;">AccomFind</span>
</td></tr>
<tr><td style="padding:32px;">
<p style="margin:0 0 8px;font-size:12px;font-weight:bold;letter-spacing:1px;color:#64748b;">ACCOMMODATION ENQUIRY</p>
<h1 style="margin:0 0 24px;font-size:24px;line-height:1.3;color:#112a46;">{title_html}</h1>
<div style="padding:20px;border-left:3px solid #1f4e79;background-color:#f8fafc;font-size:15px;line-height:1.7;word-break:break-word;">{message_html}</div>
<div style="margin-top:24px;padding-top:20px;border-top:1px solid #e2e8f0;">
<p style="margin:0 0 8px;font-size:12px;color:#64748b;">Sent from this student account</p>
<p style="margin:0 0 5px;font-size:15px;font-weight:bold;">{name_html}</p>
<p style="margin:0;font-size:14px;color:#64748b;">Verified email: <a href="{email_link}" style="color:#1f4e79;">{email_html}</a></p>
</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:28px;">
<tr><td style="background-color:#1f4e79;border-radius:8px;">
<a href="{url_html}" style="display:inline-block;padding:13px 22px;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;">View listing</a>
</td></tr></table>
</td></tr>
<tr><td style="padding:20px 32px;background-color:#f8fafc;border-top:1px solid #e2e8f0;border-radius:0 0 16px 16px;">
<p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">Reply to this email to contact the student directly.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""
    return enquiry_subject(title), plain, html
