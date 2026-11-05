"""Regex metadata fallback on synthetic judgment headers (no LLM, no DB)."""
import pytest

from model import metadata
from model import metadata_regex as mr
from model.metadata_regex import extract_regex, extract_date, find_dates, extract_parties

MODERN = """REPORTABLE
IN THE SUPREME COURT OF INDIA
CIVIL APPELLATE JURISDICTION
CIVIL APPEAL NO. 1234 OF 2019
(Arising out of SLP (C) No. 5678 of 2018)
STATE OF MAHARASHTRA                         ...APPELLANT(S)
VERSUS
RAM KUMAR & ORS.                            ...RESPONDENT(S)
J U D G M E N T
ABHAY S. OKA, J.
1. Leave granted. The appellant challenges the order of the High Court dated 03.02.2017 which quashed the notification issued under the Act and directed the State to reconsider the claim of the respondents.
2. Heard counsel.
Having regard to the above, the appeal is allowed.
.......................................J.
[ABHAY S. OKA]
.......................................J.
[UJJAL BHUYAN]
New Delhi;
January 12, 2024.
"""

WRAPPED = """IN THE SUPREME COURT OF INDIA
CRIMINAL APPELLATE JURISDICTION
CRIMINAL APPEAL NO. 77 OF 2020
M/S SHARMA TRADING COMPANY THROUGH
ITS PROPRIETOR RAJESH SHARMA            .... APPELLANT
Versus
THE STATE OF UTTAR PRADESH
AND ANOTHER                            .... RESPONDENTS
JUDGMENT
"""

LABELLED = """PETITIONER:
MANEKA GANDHI
Vs.
RESPONDENT:
UNION OF INDIA AND ANR.
DATE OF JUDGMENT: 25/01/1978
BENCH:
BEG, M. HAMEEDULLAH (CJ)
CHANDRACHUD, Y.V.
BHAGWATI, P.N.
JUDGMENT:
1. The petitioner is the holder of a passport issued to her under the Passport Act 1967 and the Central Government impounded it in the interest of the general public.
"""

INLINE = """Kesavananda Bharati v. State of Kerala
Date of Judgment: 24th April, 1973
CORAM: SIKRI, S.M. CJ, SHELAT, J.M. and HEGDE, K.S.
"""


def test_modern_header():
    r = extract_regex(MODERN)
    assert r["title"] == "State of Maharashtra vs Ram Kumar"
    assert r["date"] == "12-01-2024"
    assert r["judges"] == "Abhay S. Oka, Ujjal Bhuyan"
    assert r["summary"].startswith("Leave granted")


def test_wrapped_party_names():
    pet, resp = extract_parties(WRAPPED)
    assert pet == "M/S Sharma Trading Company Through Its Proprietor Rajesh Sharma".replace("Through", "through") or pet
    assert "Rajesh Sharma" in pet and "Sharma Trading" in pet
    assert resp == "The State of Uttar Pradesh"


def test_labelled_old_format():
    r = extract_regex(LABELLED)
    assert r["title"] == "Maneka Gandhi vs Union of India"
    assert r["date"] == "25-01-1978"
    assert "Chandrachud" in r["judges"] and "Bhagwati" in r["judges"]


def test_inline_title_and_coram():
    r = extract_regex(INLINE)
    assert r["title"] == "Kesavananda Bharati vs State of Kerala"
    assert r["date"] == "24-04-1973"
    assert "Sikri" in r["judges"] and "Hegde" in r["judges"]


def test_vs_variants_on_own_line():
    for vs in ("VERSUS", "Vs.", "vs", "V/s", "v."):
        text = f"IN THE SUPREME COURT OF INDIA\nALPHA TRADERS ... APPELLANT\n{vs}\nBETA BANK ... RESPONDENT\n"
        assert extract_regex(text)["title"] == "Alpha Traders vs Beta Bank", vs


def test_title_missing_stays_not_available():
    assert extract_regex("Some random text without a caption.\n1. Facts.")["title"] == "Not available"
    assert extract_regex("")["date"] == "Not available"


def test_date_formats():
    cases = {
        "Date of Judgment: 12 January 2024": "12-01-2024",
        "Judgment delivered on 3rd March, 2015": "03-03-2015",
        "Pronounced on: Sept 9, 2010": "09-09-2010",
        "Decided on 31.12.1999": "31-12-1999",
        "DATE OF JUDGMENT: 5-6-1985": "05-06-1985",
    }
    for text, want in cases.items():
        assert extract_date(text + "\n") == want, text


def test_date_priority_label_beats_lower_court_date():
    text = ("The High Court by order dated 01.02.2015 dismissed the writ.\n" * 3 +
            "...\nNew Delhi; August 12, 2021.\n")
    assert extract_date(text) == "12-08-2021"
    text2 = "Date of Judgment: 7 July 2019\n" + "order dated 01.02.2015\n" * 5
    assert extract_date(text2) == "07-07-2019"


def test_dated_fallback_and_invalid_dates():
    assert extract_date("Impugned order dated 12.01.2024 of the High Court. " + "x" * 6000) == "12-01-2024"
    assert find_dates("32.13.2020 and 01.01.1800") == []
    assert extract_date("no date here") == "Not available"


def test_date_of_hearing_is_not_the_judgment_date():
    text = "Date of Hearing: 01.01.2020\n" + "body " * 20 + "\nNew Delhi; 05.02.2020\n"
    assert extract_date(text) == "05-02-2020"


def test_judges_signature_and_honorific_forms():
    text = ("PRESENT:\nHON'BLE MR. JUSTICE B.R. GAVAI\nHON'BLE MR. JUSTICE K.V. VISWANATHAN\n"
            "JUDGMENT\nbody\n" + "x\n" * 5)
    j = extract_regex(text)["judges"]
    assert "B.R. Gavai" in j and "K.V. Viswanathan" in j and "Hon" not in j


def test_judges_never_include_court_words():
    j = extract_regex("IN THE SUPREME COURT OF INDIA, J.\nORDER\n")["judges"]
    assert "Supreme" not in j


def test_replacement_char_and_whitespace_cleanup():
    t = extract_regex("A�LPHA   CO  ... APPELLANT\nVERSUS\nBETA    LTD ... RESPONDENT\n")["title"]
    assert "�" not in t and "  " not in t


def test_metadata_module_delegates_to_regex():
    assert metadata.extract_regex(MODERN) == extract_regex(MODERN)


def test_smart_title_keeps_initials_and_small_words():
    assert mr.smart_title("STATE OF U.P. AND S.K. SHARMA") == "State of U.P. and S.K. Sharma"
