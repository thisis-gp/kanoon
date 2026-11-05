"""
LLM-free metadata extraction from the text of an Indian Supreme Court judgment.

Pure functions (no database, no network). Used by model.metadata as the first pass; the LLM
is an optional second pass for fields this module cannot find ("Not available").

Header shapes handled (all seen in SC judgments):
  1. Modern:   "STATE OF X ... APPELLANT(S)" / "VERSUS" / "Y & ORS. ... RESPONDENT(S)"
               (party names may wrap over several lines)
  2. Labelled: "PETITIONER: X" ... "Vs." ... "RESPONDENT: Y" ... "DATE OF JUDGMENT: 12/01/1978"
               ... "BENCH: SIKRI, S.M. (CJ), SHELAT, J.M."
  3. Inline:   "Maneka Gandhi v. Union of India" or "X vs Y" on one line.

Dates are returned as DD-MM-YYYY. Order of trust: a labelled pronouncement date
("Date of Judgment", "Judgment delivered on", "Pronounced on", "Decided on"), then the dated
signature line ("New Delhi; January 12, 2024" / "Date: 12.01.2024") near the end, then the last
date in the final lines, then "dated 12.01.2024" in the header. Best effort: the first two are
reliable, the last two can pick up a lower-court date.
"""
import re

HEAD_LINES = 70
TAIL_LINES = 70
TAIL_CHARS = 1800
PLACE_DATE_CHARS = 600
HEAD_CHARS = 5000
MAX_PARTY_LINES = 4
MAX_JUDGES = 9
MIN_YEAR, MAX_YEAR = 1947, 2030
NA = "Not available"

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MONTH_RE = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
             r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")

# ---------------- dates ----------------
_DATE_DMY_TEXT = rf"(\d{{1,2}})(?:st|nd|rd|th)?[\s,.\-]+({_MONTH_RE})\.?,?\s*(\d{{4}})"
_DATE_MDY_TEXT = rf"({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})"
_DATE_NUM = r"(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{4})"
_DATE_RX = re.compile(rf"(?<![\d/])(?:{_DATE_DMY_TEXT}|{_DATE_MDY_TEXT}|{_DATE_NUM})(?![\d])", re.I)


def _fmt(d, m, y):
    if not (MIN_YEAR <= y <= MAX_YEAR and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    return f"{d:02d}-{m:02d}-{y}"


def _date_from_match(m):
    g = m.groups()
    if g[0] is not None:                                   # 12 January 2024
        return _fmt(int(g[0]), _MONTHS[g[1][:3].lower()], int(g[2]))
    if g[3] is not None:                                   # January 12, 2024
        return _fmt(int(g[4]), _MONTHS[g[3][:3].lower()], int(g[5]))
    return _fmt(int(g[6]), int(g[7]), int(g[8]))           # 12.01.2024 (day first)


def find_dates(text):
    """[(position, 'DD-MM-YYYY')] for every valid date in text."""
    out = []
    for m in _DATE_RX.finditer(text):
        d = _date_from_match(m)
        if d:
            out.append((m.start(), d))
    return out


_LABEL_RX = re.compile(
    r"(?:date\s+of\s+(?:judg(?:e)?ment|decision|pronouncement|order)|judg(?:e)?ment\s+"
    r"(?:delivered|pronounced|reserved\s+on[^.\n]{0,40}pronounced)\s*(?:on|dated)?|"
    r"(?:pronounced|decided|delivered|reported)\s+on|decided\s+(?:on|dated)|date\s+of\s+hearing)"
    r"\s*[:\-]?\s*", re.I)
_PLACE_DATE_RX = re.compile(r"(?:New\s+Delhi|Delhi|\bDate\s*:)\s*[:;,.\-]*\s*", re.I)
_DATED_RX = re.compile(r"\bdated\s*[:\-]?\s*", re.I)


def _first_date_after(text, rx, window=45, only_before=None):
    for m in rx.finditer(text):
        seg = text[m.end(): m.end() + window]
        ds = find_dates(seg)
        if ds and ds[0][0] <= 6:                           # date must follow the label closely
            if "date of hearing" in m.group(0).lower():
                continue
            return ds[0][1]
    return None


def extract_date(text):
    head, tail = text[:HEAD_CHARS], text[-TAIL_CHARS:]
    for part in (head, tail):                              # 1. labelled pronouncement date
        d = _first_date_after(part, _LABEL_RX)
        if d:
            return d
    d = _first_date_after(text[-PLACE_DATE_CHARS:], _PLACE_DATE_RX)            # 2. signature line "New Delhi; <date>"
    if d:
        return d
    ds = find_dates(tail)                                  # 3. last date near the end
    if ds:
        return ds[-1][1]
    return _first_date_after(head, _DATED_RX) or NA        # 4. "dated 12.01.2024" in the header


# ---------------- parties / title ----------------
_VS_LINE = re.compile(r"^\W*(?:versus|v\s*/\s*s|vs\.?|v\.?)\W*$", re.I)
_VS_INLINE = re.compile(r"^(.{3,120}?)\s+(?:versus|vs\.?|v\.)\s+(.{3,120})$", re.I)
_ROLE = re.compile(r"(?:APPELLANT|PETITIONER|RESPONDENT|DEFENDANT|PLAINTIFF|COMPLAINANT|"
                   r"ACCUSED|CAVEATOR|INTERVENOR|APPLICANT|CONTEMNOR|OPPOSITE\s+PARTY)S?", re.I)
_ROLE_TAIL = re.compile(rf"[\s.…_\-–—]*[(\[]?\s*(?:\d+\w*\s+)?{_ROLE.pattern}\b.*$", re.I)
_NOISE = re.compile(
    r"SUPREME\s+COURT|JURISDICTION|\b(?:CIVIL|CRIMINAL)\s+(?:APPEAL|APPELLATE)|\bAPPEAL\s*\(?(?:CIVIL|CRL)|"
    r"\bPETITION\b|\bNO\.|\bOF\s+(?:19|20)\d{2}|REPORTABLE|J\s*U\s*D\s*G\s*M\s*E\s*N\s*T|"
    r"\bO\s*R\s*D\s*E\s*R\b|\bDATE\b|\bBENCH\b|\bCORAM\b|\bPRESENT\b|^\W*\[|ARISING|^\s*\d+\s*$", re.I)
_TAIL_PARTY = re.compile(r"[\s,&]*\b(?:ors|anr|etc|others|and\s+(?:others|another|anr|ors)|another)\b\.?\s*$", re.I)
_SMALL = {"of", "and", "the", "for", "in", "on", "at", "to", "vs", "v", "by", "through"}


def smart_title(s):
    """Title-case ALL-CAPS names but keep initials (S.K.) and small words sensible."""
    words = []
    for i, w in enumerate(s.split()):
        if re.fullmatch(r"(?:[A-Za-z]\.){1,}[A-Za-z]?\.?", w) or (len(w) <= 3 and w.isupper() and "." in w):
            words.append(w.upper())
        elif w.lower() in _SMALL and i > 0:
            words.append(w.lower())
        elif w.isupper() or w.islower():
            words.append(w[:1].upper() + w[1:].lower())
        else:
            words.append(w)
    return " ".join(words)


def _clean_party(s):
    s = re.sub(r"^\W*(?:\d+|\(\d+\)|[ivx]+)[.)]\s+", "", s.strip())
    s = _ROLE_TAIL.sub("", s)
    s = re.sub(r"[\s.…_\-–—]+$", "", s)
    s = _TAIL_PARTY.sub("", s).strip(" .-&,;:")
    s = s.replace("�", "")
    return re.sub(r"\s+", " ", s)


def _collect_lines(lines, start, step):
    """Party-name lines next to VERSUS.
    Right side (step +1): read down to and including the line with the role marker.
    Left side (step -1): the nearest line is the role line; also take wrapped lines above it
    until another role line (the previous party), header noise, or MAX_PARTY_LINES."""
    got, i = [], start
    while 0 <= i < len(lines) and len(got) < MAX_PARTY_LINES:
        line = lines[i]
        if _VS_LINE.match(line):
            break
        if _NOISE.search(line) and not (not got and _ROLE.search(line)):
            break
        if step < 0 and got and _ROLE.search(line):
            break
        got.append(line)
        if step > 0 and _ROLE.search(line):
            break
        i += step
    return got if step > 0 else got[::-1]


def extract_parties(text):
    """(petitioner, respondent) or (None, None)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    top = lines[:HEAD_LINES]
    pet = resp = None
    for i, l in enumerate(top):                            # shape 1: VERSUS on its own line
        if _VS_LINE.match(l) and 0 < i < len(top) - 1:
            pet = _clean_party(" ".join(_collect_lines(top, i - 1, -1)))
            resp = _clean_party(" ".join(_collect_lines(top, i + 1, +1)))
            if pet and resp:
                return smart_title(pet), smart_title(resp)
            pet = resp = None
    labelled = re.search(r"PETITIONER\s*:\s*(.+?)\s*(?:\n\s*)?(?:Vs\.?|Versus)\s*(?:\n\s*)?RESPONDENT\s*:\s*(.+?)"
                         r"(?:\n\s*\n|\n\s*(?:DATE|BENCH|CITATION|ACT|HEADNOTE|JUDGMENT)\b|$)",
                         "\n".join(top), re.I | re.S)       # shape 2
    if labelled:
        pet, resp = _clean_party(labelled.group(1)), _clean_party(labelled.group(2))
        if pet and resp:
            return smart_title(pet), smart_title(resp)
    for l in top:                                          # shape 3: inline
        m = _VS_INLINE.match(re.sub(r"\s+", " ", l))
        if m and not _NOISE.search(l):
            pet, resp = _clean_party(m.group(1)), _clean_party(m.group(2))
            if pet and resp:
                return smart_title(pet), smart_title(resp)
    return None, None


def extract_title(text):
    pet, resp = extract_parties(text)
    return f"{pet} vs {resp}"[:200] if pet and resp else NA


# ---------------- judges ----------------
_TITLE_TOKENS = {"HON'BLE", "HONBLE", "HONOURABLE", "THE", "MR", "MR.", "MRS", "MRS.", "MS", "MS.",
                 "DR", "DR.", "SHRI", "SMT", "SRI", "JUSTICE", "JUSTICES", "CJI", "CHIEF", "J", "J.",
                 "JJ", "JJ.", "CJ", "CJ.", "C.J.", "C.J", "AND"}
_NOT_NAME = re.compile(r"SUPREME|COURT|INDIA|JUDGMENT|ORDER|APPEAL|PETITION|DATED|BENCH|CORAM|REPORTABLE|"
                       r"VERSUS|APPELLANT|RESPONDENT", re.I)
_SIG_LINE = re.compile(r"^[.\s…_\-–—]*,?\s*(?:C\.?)?J\.?\s*,?$", re.I)
_BRACKET_NAME = re.compile(r"^[\[(]\s*([A-Za-z][A-Za-z.'\s]{2,40}?)\s*[\])]$")
_NAME_J = re.compile(r"^([A-Z][A-Za-z.'\s,]{2,40}?),?\s+(?:C\.?)?J\.?$")
_LABEL_BENCH = re.compile(r"^\W*(?:BENCH|CORAM|PRESENT)\s*[:\-]\s*(.*)$", re.I)
_LABEL_LINE = re.compile(r"^[A-Z][A-Z\s/]{2,25}:")
_BENCH_SPLIT = re.compile(r"\s*(?:;|\band\b|&|(?<=\bCJ),|(?<=C\.J\.),|(?<=\)),)\s*", re.I)


def _clean_judge(s):
    """'SHELAT, J.M.' -> 'J.M. Shelat'; 'HON'BLE MR. JUSTICE B.R. GAVAI' -> 'B.R. Gavai'."""
    s = re.sub(r"\([^)]*\)", " ", s)                        # (CJ), (J) ...
    s = re.sub(r"[^A-Za-z.',\s]", " ", s)
    toks = [t for t in s.split() if t.strip(",").upper() not in _TITLE_TOKENS]
    s = " ".join(toks).strip(" ,")
    if "," in s:                                            # surname-first
        surname, rest = [p.strip() for p in s.split(",", 1)]
        s = f"{rest} {surname}".strip() if rest and "," not in rest else s.replace(",", " ")
    s = re.sub(r"\s+", " ", s).strip(" .,'")
    if len(s) < 3 or _NOT_NAME.search(s) or len(s.split()) > 5:
        return None
    return smart_title(s)


def _judges_from_bench_text(txt):
    return [n for n in (_clean_judge(p) for p in _BENCH_SPLIT.split(txt)) if n]


def extract_judges(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    head, tail = lines[:HEAD_LINES], lines[-TAIL_LINES:]
    found = []
    for i, l in enumerate(head):                           # BENCH:/CORAM:/PRESENT: blocks
        m = _LABEL_BENCH.match(l)
        if not m:
            continue
        if m.group(1).strip():
            found += _judges_from_bench_text(m.group(1))
            continue
        for nxt in head[i + 1: i + 1 + MAX_JUDGES]:       # one judge per following line
            if _LABEL_LINE.match(nxt) or re.search(r"\d|JUDGMENT|ORDER", nxt):
                break
            found += _judges_from_bench_text(nxt)
    for l in head:                                         # "HON'BLE MR. JUSTICE X" lines
        if re.search(r"JUSTICE", l, re.I) and len(l) < 90:
            n = _clean_judge(l)
            if n:
                found.append(n)
    for l in head + tail:                                  # "ABHAY S. OKA, J."
        m = _NAME_J.match(l)
        if m:
            n = _clean_judge(m.group(1))
            if n:
                found.append(n)
    for i, l in enumerate(tail[:-1]):                      # "....J." followed by "[NAME]"
        if _SIG_LINE.match(l):
            m = _BRACKET_NAME.match(tail[i + 1])
            n = _clean_judge(m.group(1)) if m else None
            if n:
                found.append(n)
    uniq = list(dict.fromkeys(found))[:MAX_JUDGES]
    return ", ".join(uniq) if uniq else NA


# ---------------- summary + entry point ----------------
def extract_summary(text):
    sm = re.search(r"(?:^|\n)\s*1\.\s+(.{60,700}?)(?:\n\s*2\.|\Z)", text, re.S)
    return re.sub(r"\s+", " ", sm.group(1)).strip()[:400] if sm else NA


def _tidy(v):
    v = re.sub(r"\s+", " ", v.replace("�", "")).strip(" -,")
    return v or NA


def extract_regex(text):
    """{title, judges, date, summary}; "Not available" for anything not found."""
    return {k: _tidy(v) for k, v in {
        "title": extract_title(text), "judges": extract_judges(text),
        "date": extract_date(text), "summary": extract_summary(text)}.items()}
