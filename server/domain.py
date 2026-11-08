"""Pure project rules used by the API and by offline regression tests."""
import hashlib
import hmac
import math
import re
import secrets
from collections import Counter
from datetime import date, timedelta


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024**2)
    return salt + "." + digest.hex()


def password_matches(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(".")[0]), stored)


def chunks(text, size=1400):
    return [text[i:i+size] for i in range(0, len(text), size-120) if text[i:i+size].strip()]


def retrieve(rows, query, limit=10):
    terms = set(re.findall(r"\w+", query.casefold())) - {"what","which","the","does","are","how","and","for","our"}
    ranked = []
    for row in rows:
        tokens = Counter(re.findall(r"\w+", (row["title"]+" "+row["body"]).casefold()))
        score = sum(1 + math.log(tokens[t]) for t in terms if tokens[t])
        if score and row["state"] != "superseded":
            ranked.append((row["state"] == "approved", score, row["id"], row))
    return [item[-1] for item in sorted(ranked, key=lambda r:r[:3], reverse=True)[:limit]]


def working_schedule(tasks, capacities, start, target=None):
    """Conservative whole-working-day schedule. Hours include review and QA."""
    remaining = {t["key"]: t for t in tasks}
    if len(remaining) != len(tasks):
        raise ValueError("Duplicate task key")
    bookings, ends, result = {}, {}, []
    while remaining:
        ready = [t for t in remaining.values() if set(t["depends_on"]) <= ends.keys()]
        if not ready:
            raise ValueError("Unknown dependency or dependency cycle")
        for task in ready:
            key, owner, hours = task["key"], task["owner"], task["hours"]
            cap = capacities.get(owner, 0)
            if not 0.25 <= cap <= 24 or not 0 < hours <= 10000:
                raise ValueError("Positive effort and available hours are required")
            day = max([start, bookings.get(owner, start)] + [ends[d]+timedelta(days=1) for d in task["depends_on"]])
            while day.weekday() >= 5: day += timedelta(days=1)
            begin = day
            for _ in range(math.ceil(hours/cap)-1):
                day += timedelta(days=1)
                while day.weekday() >= 5: day += timedelta(days=1)
            ends[key] = day
            bookings[owner] = day + timedelta(days=1)
            result.append(dict(task, start=str(begin), due=str(day), late=bool(target and day > target)))
            del remaining[key]
    return result
