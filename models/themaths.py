from collections import Counter
from datetime import datetime

# Sample: your roster data loaded as a list of dicts
roster_data = [...]  # replace with your actual data

# Target leave types
target_types = ["PSL", "PNW", "TRE"]

# Initialize counters
day_patterns = {t: Counter() for t in target_types}

# Analyze each entry
for entry in roster_data:
    type_shift = entry.get("type_shift")
    if type_shift in target_types:
        date_str = entry["date"]
        day_name = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
        day_patterns[type_shift][day_name] += 1

# Print results
for leave_type, counter in day_patterns.items():
    print(f"\n{leave_type} patterns:")
    for day, count in sorted(counter.items()):
        print(f"  {day}: {count}")
