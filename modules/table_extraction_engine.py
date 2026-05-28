import io
import re
import pandas as pd


TABLE_KEYWORDS = {
    "top_taxpayers": [
        "top taxpayers",
        "largest taxpayers",
        "principal taxpayers",
        "major taxpayers",
        "taxpayer concentration",
    ],
    "overlapping_debt": [
        "overlapping debt",
        "direct and overlapping debt",
        "statement of overlapping debt",
    ],
    "reserve_fund": [
        "reserve fund",
        "initial reserve",
        "reserve account",
    ],
    "debt_service": [
        "debt service",
        "annual debt service",
        "debt service schedule",
        "cashflow",
    ],
}


def safe_text(value):
    return "" if value is None else str(value)


def extract_numbers(text):
    return re.findall(r"\$?\s?[\d,]+(?:\.\d+)?%?", safe_text(text))


def detect_candidate_pages(parsed_docs):
    """
    Works with your existing parsed_documents structure.
    No new PDF dependency required.
    """
    candidates = []

    for doc in parsed_docs or []:
        doc_name = doc.get("file_name", "Uploaded document")
        text = safe_text(doc.get("text", ""))
        lower = text.lower()

        for label, phrases in TABLE_KEYWORDS.items():
            score = 0
            hits = []

            for phrase in phrases:
                if phrase in lower:
                    score += 1
                    hits.append(phrase)

            if score > 0:
                candidates.append(
                    {
                        "document": doc_name,
                        "candidate_type": label,
                        "score": score,
                        "matched_terms": hits,
                        "preview": text[:2500],
                    }
                )

    return sorted(candidates, key=lambda x: x["score"], reverse=True)


def reconstruct_taxpayer_table_from_text(text):
    rows = []

    for line in safe_text(text).splitlines():
        line = line.strip()
        if not line:
            continue

        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if not pct_match:
            continue

        pct = float(pct_match.group(1))
        name = line.replace(pct_match.group(0), "").strip(" -—|:\t")

        if len(name) >= 3:
            rows.append(
                {
                    "taxpayer_name": name,
                    "levy_percent": pct,
                }
            )

    return pd.DataFrame(rows)


def extract_vtl_inputs_from_text(text):
    text = safe_text(text)

    def find_amount(patterns):
        for pattern in patterns:
            match = re.search(pattern, text, re.I | re.S)
            if match:
                raw = match.group(1)
                return float(raw.replace(",", ""))
        return None

    assessed_value = find_amount(
        [
            r"assessed value[^$]{0,120}\$?\s*([\d,]+)",
            r"total assessed value[^$]{0,120}\$?\s*([\d,]+)",
        ]
    )

    direct_debt = find_amount(
        [
            r"direct debt[^$]{0,120}\$?\s*([\d,]+)",
            r"bonds outstanding[^$]{0,120}\$?\s*([\d,]+)",
        ]
    )

    overlapping_debt = find_amount(
        [
            r"overlapping debt[^$]{0,120}\$?\s*([\d,]+)",
            r"total overlapping[^$]{0,120}\$?\s*([\d,]+)",
        ]
    )

    return {
        "assessed_value": assessed_value,
        "direct_debt": direct_debt,
        "overlapping_debt": overlapping_debt,
    }


def extract_mltm_cashflow_from_text(text):
    rows = []

    for line in safe_text(text).splitlines():
        nums = re.findall(r"[\d,]+(?:\.\d+)?", line)
        year_match = re.search(r"\b(20\d{2})\b", line)

        if year_match and len(nums) >= 3:
            try:
                year = int(year_match.group(1))
                values = [float(x.replace(",", "")) for x in nums if x != str(year)]
                if len(values) >= 2:
                    rows.append(
                        {
                            "year": year,
                            "special_tax_levy": values[0],
                            "annual_debt_service": values[1],
                        }
                    )
            except Exception:
                pass

    return pd.DataFrame(rows)


def confidence_score(found_value_count, expected_count, source_match=True):
    if expected_count == 0:
        return 0

    base = found_value_count / expected_count
    score = int(base * 80)

    if source_match:
        score += 20

    return min(score, 100)


def confidence_status(score):
    if score >= 90:
        return "high_confidence"
    if score >= 70:
        return "needs_review"
    return "low_confidence"
