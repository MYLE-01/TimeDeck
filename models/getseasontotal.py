from datetime import datetime, date ,timedelta

# --- Helpers --------------------------------------------------------

def normalize_date(date_str):
    """Convert various date formats into a proper date object."""
    if isinstance(date_str, date):
        return date_str
    if not date_str:
        return datetime.now().date()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")

def parseDateDDMMYYYY(date_str):
    """Parse a date in either dd/mm/yyyy or dd-mm-yyyy format."""
    if isinstance(date_str, date):
        return date_str
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")

def minToHrs(mins):
    """Convert minutes to H:MM format"""
    h, m = divmod(int(mins), 60)
    return f"{h}:{m:02d}"


def sumMinutesBetween(data, startDate, endDate, rollOverNights=False):
    """Sum minutes between two dates (inclusive), with optional night shift rollover."""
    start = normalize_date(startDate)
    end = normalize_date(endDate) + timedelta(days=1)  # inclusive range

    total = 0
    for entry in data:
        entryDate = normalize_date(entry["date"])
        addMins = entry.get("mins", 0)

        # ⏰ Night shift rollover
        if rollOverNights and entry.get("shift_type") == "Night":
            rolledDate = entryDate + timedelta(days=1)
            # Only roll forward if within the range
            if rolledDate <= end:
                entryDate = rolledDate

        # ✅ Only count if within range
        if start <= entryDate < end:
            total += addMins

    return total


# --- Main -----------------------------------------------------------

def getSeasonTotals(data, config, referenceDate=None, rollOverNights=False):
    refDate = normalize_date(referenceDate or datetime.now().date())

    seasonStart = parseDateDDMMYYYY(config["season"]["start"])
    seasonEnd = parseDateDDMMYYYY(config["season"]["ends"])
    totaltodo = config.get("default_entitlement_mins", 0)
    isTemp = not totaltodo or totaltodo == 0

    # 1️⃣ Actual minutes so far
    minsSoFar = sumMinutesBetween(data, seasonStart, refDate, rollOverNights)

    # 2️⃣ Expected so far
    seasonDays = (seasonEnd - seasonStart).days + 1
    daysPassed = (refDate - seasonStart).days + 1

    # 3️⃣ Remaining + makeup
    tomorrow = refDate + timedelta(days=1)
    minsRemaining = sumMinutesBetween(data, tomorrow, seasonEnd, rollOverNights)

    if isTemp:
        totaltodo = minsRemaining + minsSoFar

    today = datetime.now().date()
    outsideSeason = today < seasonStart or today > seasonEnd

    if isTemp and outsideSeason:
        return {
            "totaltodo": 0,
            "minsSoFar": 0,
            "isTemp": True,
            "expectedSoFar": 0,
            "minsRemaining": 0,
            "makeup": 0,
            "xtraShift": "0.0",
            "totalSeason": 0,
            "progressPct": "0.0",
            "expectedPct": "0.0",
            "behindPct": "0.0",
            "behindHours": "0.0",
            "behindMins": "0.0",
            "display": {
                "totalToDo": "0:00",
                "totalSoFar": "0:00",
                "totalRemaining": "0:00",
                "behindHours": "0.0",
                "progressPctText": "0% complete",
                "expectedPctText": "Out of season",
                "behindPctText": "—",
                "makeupText": "0.0 Covers"
            },
            "statusMsg": "📅 No active season"
        }

    expectedSoFar = round((daysPassed / seasonDays) * totaltodo)
    makeup = totaltodo - (minsSoFar + minsRemaining)
    xtraShift = f"{makeup / 720:.1f}"

    progressPct = f"{(minsSoFar / totaltodo) * 100:.1f}" if totaltodo else "0.0"
    expectedPct = f"{(expectedSoFar / totaltodo) * 100:.1f}" if totaltodo else "0.0"

    behindMins = minsSoFar - expectedSoFar
    behindPct = f"{(behindMins / totaltodo) * 100:.1f}" if totaltodo else "0.0"

    # 4️⃣ Callback minutes (CB shifts)
    callbackMins = sum(
        e.get("mins", 0)
        for e in data
        if e.get("type_shift") == "CB"
        and normalize_date(e["date"]) <= refDate
    )

    return {
        "totaltodo": totaltodo,
        "minsSoFar": minsSoFar,
        "isTemp": isTemp,
        "expectedSoFar": expectedSoFar,
        "minsRemaining": minsRemaining,
        "makeup": makeup,
        "xtraShift": xtraShift,
        "totalSeason": minsSoFar + minsRemaining,
        "progressPct": progressPct,
        "expectedPct": expectedPct,
        "behindPct": behindPct,
        "behindHours": f"{abs(behindMins) / 60:.1f}",
        "behindMins": behindMins,

        "display": {
            "totalToDo": minToHrs(totaltodo),
            "totalSoFar": minToHrs(minsSoFar),
            "totalRemaining": minToHrs(minsRemaining),
            "behindHours": f"{abs(behindMins) / 60:.1f}",
            "progressPctText": f"{progressPct}% complete",
            "expectedPctText": f"Should be at {expectedPct}%",
            "behindHours": f"{abs(behindMins) / 60:.1f}",
            "behindMins": behindMins,
            "behindPctText": (
                f"Ahead by {behindPct}%" if behindMins > 0
                else f"Behind by {abs(float(behindPct))}%"
            ),
            "makeupText": f"{xtraShift} Covers"
        }

    }
