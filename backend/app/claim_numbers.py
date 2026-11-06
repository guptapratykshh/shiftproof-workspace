"""Bounded normalization of explicitly spoken numbers, without guessing ASR text.

Unrecognized words and ambiguous digit sequences stay unchanged. Original
transcripts are never rewritten; this is only for grounding and comparison.
"""
import re

VALUES = {}
for value, words in {
    0: "zero शून्य", 1: "one एक ek", 2: "two दो", 3: "three तीन teen",
    4: "four चार char chaar", 5: "five पाँच पांच panch paanch", 6: "six छह छः chhe",
    7: "seven सात saat", 8: "eight आठ aath", 9: "nine नौ nau", 10: "ten दस das",
    11: "eleven ग्यारह gyarah", 12: "twelve बारह barah", 13: "thirteen तेरह terah",
    14: "fourteen चौदह chaudah", 15: "fifteen पंद्रह पन्द्रह pandrah",
    16: "sixteen सोलह solah", 17: "seventeen सत्रह satrah", 18: "eighteen अठारह atharah",
    19: "nineteen उन्नीस unnis", 20: "twenty बीस bees", 25: "पच्चीस pachis pachchis",
    30: "thirty तीस tees", 35: "पैंतीस paintis", 40: "forty चालीस chalis chaalis",
    45: "पैंतालीस paintalis", 50: "fifty पचास pachas pachaas", 55: "पचपन pachpan",
    60: "sixty साठ", 65: "पैंसठ painsath", 70: "seventy सत्तर sattar",
    75: "पचहत्तर pachhattar", 80: "eighty अस्सी assi", 85: "पचासी pachasi pachaasi",
    90: "ninety नब्बे nabbe", 95: "पंचानवे panchanve",
}.items():
    VALUES.update({word: value for word in words.split()})
SCALES = {"hundred": 100, "सौ": 100, "sau": 100, "thousand": 1000, "हजार": 1000,
          "हज़ार": 1000, "hazar": 1000, "hazaar": 1000, "lakh": 100000, "लाख": 100000}
WORDS = re.compile(r"(?<!\w)(?:" + "|".join(sorted([*VALUES, *SCALES], key=len, reverse=True)) + r")(?!\w)", re.I)


def number_value(words):
    total = current = 0
    previous = None
    for word in words:
        if word in SCALES:
            scale = SCALES[word]
            current = (current or 1) * scale
            if scale >= 1000:
                total += current
                current = 0
            previous = None
        else:
            value = VALUES[word]
            if previous is not None and not (previous >= 20 and previous % 10 == 0 and 0 < value < 10):
                return None
            current += value
            previous = value
    return total + current


def spoken_numbers(text):
    matches = list(WORDS.finditer(text))
    groups = []
    for match in matches:
        if groups and re.fullmatch(r"[\s-]+", text[groups[-1][-1].end():match.start()]):
            groups[-1].append(match)
        else:
            groups.append([match])
    for group in reversed(groups):
        value = number_value([match.group().casefold() for match in group])
        if value is not None:
            text = text[:group[0].start()] + str(value) + text[group[-1].end():]
    return text
