"""Header safety and HTML/text alternatives for student-controlled content."""
from email.message import EmailMessage
from html.parser import HTMLParser

import pytest
from app.services.enquiry_email import build_enquiry_email, enquiry_subject


@pytest.mark.parametrize("title", ["Rise Student Living\r\nBcc: other@example.test", "\x00Rise\x1f Living\u202e", "Room " * 100])
def test_subject_is_bounded_and_cannot_inject_headers(title):
    subject = enquiry_subject(title)
    message = EmailMessage()
    message["Subject"] = subject
    assert len(subject) <= 100
    assert not any(ord(char) < 32 for char in subject)
    assert message["Bcc"] is None
    assert subject.startswith("Accommodation enquiry: ")


def test_empty_title_has_readable_fallback_without_internal_id():
    assert enquiry_subject(" \r\n ") == "Accommodation enquiry: Student accommodation"


def test_html_escapes_user_content_and_preserves_message_paragraphs():
    body = 'Hi,\n\nWhen do applications open?\n\nBest\nDikeledi <script>alert("x")</script>'
    subject, plain, html = build_enquiry_email('Rise & "Living" <img src=x>',
        "https://accomfind.vercel.app/listings/9", "Account <Name>", "student@example.test", body)
    assert body in plain
    assert "Sent from this student account" in plain
    assert '<script>' not in html and '<img src=x>' not in html
    assert "&lt;script&gt;" in html and "Account &lt;Name&gt;" in html
    assert "Hi,<br>\n<br>\nWhen do applications open?" in html
    assert "The student consented" not in plain and "The student consented" not in html
    assert "listing #9" not in subject

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.urls.append(dict(attrs)["href"])
    links = Links()
    links.feed(html)
    assert links.urls == ["mailto:student@example.test", "https://accomfind.vercel.app/listings/9"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,test", "/listings/9"])
def test_listing_button_rejects_non_http_links(url):
    with pytest.raises(ValueError):
        build_enquiry_email("Test listing", url, "Student", "student@example.test", "Test enquiry")
