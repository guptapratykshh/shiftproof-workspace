"""Ground count nouns and process stages without inventing operational identifiers."""

import re
import unicodedata

from ..claim_numbers import spoken_numbers


def product_key(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    aliases = {
        "किचन": "kitchen",
        "उत्पादों": "products",
        "उत्पाद": "products",
        "प्रोडक्ट्स": "products",
        "प्रोडक्ट": "products",
        "प्रोडक्टों": "products",
    }
    for source, target in sorted(aliases.items(), key=lambda pair: -len(pair[0])):
        text = text.replace(source, target)
    text = re.sub(r"\b(?:products?|items?)\b", "item", text)
    text = re.sub(r"(?<!\w)(?:के|की|का|ki|ke|ka)(?!\w)", " ", text)
    return " ".join(re.sub(r"[^\w\s\u0900-\u097f]", " ", text).split())


def normalize_count_fields(fields, text, *, stage=False):
    """Derived suggestions only; never writes an old report or changes a count."""
    result = dict(fields)
    words = spoken_numbers(unicodedata.normalize("NFKC", text).casefold())
    if result.get("quantity") is not None and not result.get("unit"):
        # Countable nouns explicitly attached to this number mean individual items.
        # Boxes and weights remain different units, even if they contain products.
        for match in re.finditer(
            r"(?<![\w.-])(\d+(?:\.\d+)?)\s+((?:[a-z]+\s+){0,2})(products?|items?|pieces?|pcs|प्रोडक्ट्स|प्रोडक्ट|उत्पादों|उत्पाद|पीस)(?!\w)",
            words,
        ):
            if float(match[1]) == result["quantity"] and not re.search(
                r"\b(?:boxes?|kg|grams?|litres?|liters?|packs?)\b", match[2]
            ):
                result["unit"] = "pieces" if match[3] in {"piece", "pieces", "pcs", "पीस"} else "items"
                break
        if (
            not result.get("unit")
            and not re.search(r"\b(?:boxes?|kg|grams?|litres?|liters?|packs?)\b|बॉक्स|किलो", words)
            and re.search(r"(?:products?|items?|प्रोडक्ट्स|उत्पादों|उत्पाद).{0,15}(?:गिनती|count)", words)
        ):
            result["unit"] = "items"
    if stage:
        clauses = re.split(r"[,।.!;]|\b(?:but|and)\b|लेकिन|और", words)

        def affirmative(clause):
            return not re.search(
                r"\b(?:not|nahi|nahin|pending|will|would|could|should|may)\b|नहीं|बाकी|होंगे|होगा|हो जाए", clause
            )

        packed = any(
            affirmative(clause)
            and re.search(r"\b(?:packaging|packing|packed)\b|पैकिंग|पैकेजिंग", clause)
            and re.search(
                r"\b(?:packed|complete|completed|done)\b|हो चुकी|हो चुके|हो गई|हो गयी|हो गया|ho chuki|ho gayi|ho gai|ho gaya",
                clause,
            )
            for clause in clauses
        )
        ready = any(
            affirmative(clause)
            and re.search(r"dispatch.{0,22}ready|ready.{0,15}(?:for\s+)?dispatch|डिस्पैच.{0,20}तैयार", clause)
            for clause in clauses
        )
        if packed and result.get("quantity_stage") in {None, "manufactured", "packed", "ready_for_dispatch"}:
            result["quantity_stage"] = "packed"
        elif ready and result.get("quantity_stage") in {None, "manufactured", "dispatched"}:
            result["quantity_stage"] = "ready_for_dispatch"
        if ready:
            result["dispatch_status"] = "pending"
    return result
