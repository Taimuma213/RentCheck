"""Reads uploaded PDFs and checks them against the system's IDEAL formats.

IDEAL RENTAL AGREEMENT (one labelled line per item):
    Landlord Name: <name>
    Property Address: <address>
    Security Deposit Refund: ... refunded ... within 30 days ...        <- needs a time period or an amount
    Notice Period: ... 60 days written notice ...                        <- needs a time period
    Maintenance Duty: The landlord is responsible for ... repairs ...    <- needs who is responsible

    Deposit refund / Notice period / Maintenance duty result:
      Have    = the clause is there AND has clear details
      Unclear = the clause is there but vague (no days/amount, or nobody named as responsible)
      Missing = the clause is not in the PDF at all

IDEAL OWNERSHIP PAPER (all four labelled lines must exist and have a value):
    Owner Name: <name>
    Property Address: <address>
    Deed Number: <number>
    Registration Date: <date>
"""
import re

from pypdf import PdfReader

CLAUSES = ["Deposit refund", "Notice period", "Maintenance duty"]
OWNERSHIP_LABELS = {"Owner Name": r"owner\s+name", "Property Address": r"property\s+address",
                    "Deed Number": r"deed\s+(?:number|no\.?)", "Registration Date": r"registration\s+date"}

_NUMBER_WORDS = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|thirty|forty|sixty|ninety)"
_TIME_PERIOD = re.compile(rf"(?:\d+|{_NUMBER_WORDS})\s*(?:\(\d+\)\s*)?(?:day|days|week|weeks|month|months)\b", re.I)
_MONEY = re.compile(r"(?:tk\.?|bdt|taka)\s*[\d,]+|[\d,]+\s*(?:tk|taka)\b", re.I)
_PARTY = re.compile(r"\b(?:landlord|tenant|owner|lessor|lessee)\b", re.I)
_DUTY_WORD = re.compile(r"\b(?:responsible|shall|must|will|bear|bears|pay|pays|undertake|undertakes)\b", re.I)
_LABEL_START = re.compile(r"^[A-Za-z][A-Za-z ]{2,32}:")


def read_pdf_text(path):
    """Return the text inside a PDF, or '' if it cannot be read (scanned image, damaged file...)."""
    try:
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception:
        return ""


def logical_lines(text):
    """Join lines that were wrapped by the PDF so one labelled item stays on one line."""
    lines = []
    for raw in text.splitlines():
        raw = " ".join(raw.split())
        if not raw:
            continue
        if lines and not _LABEL_START.match(raw) and not lines[-1].endswith((".", ":", "!", "?")):
            lines[-1] += " " + raw
        else:
            lines.append(raw)
    return lines


def _find_value(lines, label_pattern):
    pattern = re.compile(rf"^{label_pattern}\s*:\s*(.+)$", re.I)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ""


def _sentences(lines):
    out = []
    for line in lines:
        out.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip())
    return out


def _judge(sentences, topic, is_clear):
    """Missing if no sentence is about the topic, Have if one is clear, otherwise Unclear."""
    related = [s for s in sentences if topic(s)]
    if not related:
        return "Missing"
    return "Have" if any(is_clear(s) for s in related) else "Unclear"


def parse_agreement(text):
    """Return name, address and the three clause results found in a rental agreement text."""
    lines = logical_lines(text)
    sentences = _sentences(lines)
    return {
        "name": _find_value(lines, r"(?:landlord|lessor|owner)(?:\s+name)?"),
        "address": _find_value(lines, r"(?:property\s+)?address"),
        "conditions": {
            "Deposit refund": _judge(
                sentences,
                lambda s: re.search(r"deposit", s, re.I) and re.search(r"refund|return", s, re.I),
                lambda s: _TIME_PERIOD.search(s) or _MONEY.search(s)),
            "Notice period": _judge(
                sentences,
                lambda s: re.search(r"notice", s, re.I),
                lambda s: _TIME_PERIOD.search(s)),
            "Maintenance duty": _judge(
                sentences,
                lambda s: re.search(r"maintenance|maintain|repair", s, re.I),
                lambda s: _PARTY.search(s) and _DUTY_WORD.search(s)),
        },
    }


def parse_ownership(text):
    """Check the ownership paper format and pull out the owner name and address."""
    lines = logical_lines(text)
    found = {label: _find_value(lines, pattern) for label, pattern in OWNERSHIP_LABELS.items()}
    missing = [label for label, value in found.items() if not value]
    return {"format": "Invalid Format" if missing else "Valid Format", "missing_fields": missing,
            "name": found["Owner Name"], "address": found["Property Address"]}


def same_text(a, b):
    """Case-insensitive comparison that ignores extra spaces and punctuation."""
    clean = lambda t: " ".join(re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).split())
    return clean(a) == clean(b)
