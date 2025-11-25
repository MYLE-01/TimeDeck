###############################################################
# this  build a time 
#[Season Start] ────────────────▶ [Today] ────────────────▶ [Projected Finish]
#                          ▲                          ▲
#                     [Surplus Block]           [Leave Request?]
#
################################################################
from email.quoprimime import quote
from markupsafe import Markup
from datetime import datetime,timedelta
from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


from models.roster import load_roster, generate_roster, build_roster, load_all_rosters, load_roster_for_employee
from utils.io import load_shifts , load_json, save_roster, save_json, load_roster_this_season 
from models.employee import can_edit , get_code_sets , _to_minutes , _parse_date , load_all_employees, get_active_managers, build_reporting_tree , build_cover_report

def format_date_nz(date_str):
    try:
        dt = parse_date(date_str)
        return dt.strftime("%b %d, %Y")
    except Exception:
        return date_str

def parse_date(date_str):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")

def sum_total_entitlements(draw_down_codes, annual_entitlements_carryover):
    total_carryover = sum(
        v for k, v in annual_entitlements_carryover.items()
        if k in draw_down_codes
    )
    return {
        "drawdown_total": 0,  # or remove this if not needed
        "carryover_total": total_carryover,
        "combined_total": total_carryover
    }


def sum_drawdown_minutes(roster_entries, draw_down_codes):
    if isinstance(draw_down_codes, dict):
        valid_codes = set(draw_down_codes.keys())
    elif isinstance(draw_down_codes, list):
        valid_codes = set(draw_down_codes)
    else:
        valid_codes = set()
    return sum(
        entry["mins"]
        for entry in roster_entries
        if entry.get("type_shift") in valid_codes
    )

def get_roster_date(entry):
    date = datetime.strptime(entry["date"], "%Y-%m-%d")
    if entry.get("shift_type") == "Night":
        date += timedelta(days=1)
    return date

def trace_surplus_window(roster_entries, last_day_str, surplus_hours):
    surplus_mins = surplus_hours * 60
    total = 0
    #last_day = datetime.strptime(last_day_str, "%Y-%m-%d")
    last_day = parse_date(last_day_str)
    sorted_entries = sorted(
        [e for e in roster_entries if "date" in e and "mins" in e],
        key=lambda e: e["date"],
        reverse=True
    )

    included_entries = []
    for entry in sorted_entries:
        entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        if entry.get("shift_type") == "Night":
            entry_date += timedelta(days=1)
        if entry_date <= last_day:
            total += entry["mins"]
            included_entries.append(entry)
            if total >= surplus_mins:
                break

    if not included_entries:
        return None

    return included_entries[-1]["date"]

def calculate_pacing(roster_entries, season_start_str, season_end_str, today_str, total_required_minutes):
    season_start = parse_date(season_start_str)
    season_end = parse_date(season_end_str)
    today = parse_date(today_str)

    past_entries = [e for e in roster_entries if get_roster_date(e) <= today]
    minutes_done = sum(e["mins"] for e in past_entries)

    days_elapsed = (today - season_start).days
    if days_elapsed == 0:
        return {"status": "Too early to pace"}

    rate = minutes_done / days_elapsed
    remaining = total_required_minutes - minutes_done
    days_needed = remaining / rate if rate > 0 else float("inf")
    raw_finish = today + timedelta(days=days_needed)
    projected_finish = min(raw_finish, season_end)

    total_days = (season_end - season_start).days
    expected_minutes = (days_elapsed / total_days) * total_required_minutes
    delta_minutes = minutes_done - expected_minutes

    surplus_block_start = None
    if delta_minutes > 0:
        surplus_block_start = trace_surplus_window(roster_entries, today_str, delta_minutes / 60)
    #print(f"Raw projected finish: {raw_finish}")
    #print(f"Capped projected finish: {projected_finish}")
    return {
        "season_start": season_start_str,
        "season_end": season_end_str,
        "today": today_str,
        "projected_finish": projected_finish.strftime("%Y-%m-%d"),
        "minutes_done": minutes_done,
        "delta_minutes": delta_minutes,
        "surplus_block_start": surplus_block_start
    }

def Timeline(emp_id):
    # print("Generating Timeline Block...")
    # print(f"Generating Timeline for EMP ID: {emp_id}")

    empconfig = load_json(f"emp_{emp_id}.json")
    draw_down_codes = empconfig.get("draw_down_codes", [])
    total_mins_to_do = empconfig.get("default_entitlement_mins", 139500)
    annual_entitlements_carryover = empconfig.get("annual_entitlements_carryover", {})
    carryover_total = sum(v for k, v in annual_entitlements_carryover.items() if k in draw_down_codes)
    combined_total = carryover_total

    roster_entries = load_roster_this_season(emp_id)
    roster_entries = sorted(roster_entries, key=get_roster_date, reverse=True)
    total_rostered_mins = sum(entry.get("mins", 0) for entry in roster_entries)

    first_shift_date = get_roster_date(roster_entries[-1]) if roster_entries else None
    last_shift_date = get_roster_date(roster_entries[0]) if roster_entries else None

    first_shift_fmt = format_date_nz(first_shift_date.strftime("%Y-%m-%d")) if first_shift_date else "—"
    last_shift_fmt = format_date_nz(last_shift_date.strftime("%Y-%m-%d")) if last_shift_date else "—"
    total_drawdown_mins = sum_drawdown_minutes(roster_entries, draw_down_codes)
    #print(f"draw_down_codes: {draw_down_codes}")
    #print(f"First Shift Date: {first_shift_fmt}")
    #print(f"Last Shift Date: {last_shift_fmt}")
    #print(f"Carryover Total Entitlement Minutes: {carryover_total}")
    #print(f"Combined Total Entitlement Minutes: {combined_total}")
    #print(f"Total Drawdown Minutes: {total_drawdown_mins}")

    remaining_mins = combined_total - total_drawdown_mins
    #print(f"Remaining Days: {(remaining_mins/60)/12}")

    season = empconfig.get("season", {})
    default_mins = season.get("mins", 720)
    season_start_str = season.get("start")
    season_end_str = season.get("ends")
    season_start = parse_date(season_start_str)
    season_end = parse_date(season_end_str)

    today = datetime.today()
    today_str = today.strftime("%Y-%m-%d")

    live_pacing = calculate_pacing(
        roster_entries=roster_entries,
        season_start_str=season_start_str,
        season_end_str=season_end_str,
        today_str=today_str,
        total_required_minutes=total_mins_to_do
    )



    pacing = calculate_pacing(
        roster_entries=roster_entries,
        season_start_str=season_start_str,
        season_end_str=season_end_str,
        today_str=season_end_str,
        total_required_minutes=total_mins_to_do
    )

    #print(f"Pacing Data: {pacing}")

    season_start_fmt = format_date_nz(season_start_str)
    today_fmt = format_date_nz(today_str)
    projected_finish_fmt = format_date_nz(pacing.get("projected_finish", "—"))
    surplus_start_fmt = format_date_nz(pacing.get("surplus_block_start", "—"))

    def compute_leave_finish(roster, leave_mins, season_end_date):
        grouped = defaultdict(int)
        end = parse_date(season_end_date)
        for entry in roster:
            entry_date = get_roster_date(entry)
            if entry_date <= end:
                grouped[entry_date.strftime("%Y-%m-%d")] += entry.get("mins", 0)
        sorted_dates = sorted(grouped.keys(), reverse=True)
        total = 0
        for date_str in sorted_dates:
            total += grouped[date_str]
            if total >= leave_mins:
                return date_str
        return None

    leave_finish_date = compute_leave_finish(roster_entries, remaining_mins, season_end_str)
    leave_finish_fmt = format_date_nz(leave_finish_date or "—")


    # 🧮 Helper to calculate marker position as percentage
    def date_to_percent(date_str, start, end):
        try:
            date = parse_date(date_str)
            total_span = (end - start).days
            offset = (date - start).days
            return max(0, min(100, (offset / total_span) * 100))
        except:
            return 0

    surplus_percent = date_to_percent(live_pacing.get("surplus_block_start"), season_start, season_end)
    leave_finish_percent = date_to_percent(leave_finish_date, season_start, season_end)
    leave_finish_dt = parse_date(leave_finish_date)
    season_end_dt = parse_date(season_end_str)
    days_diff = (season_end_dt - leave_finish_dt).days
    if days_diff > 0:
        pacing_note = f"Leave Starts {days_diff} day(s) before season end"
    elif days_diff < 0:
        pacing_note = f"Leave Starts {abs(days_diff)} day(s) after season end"
    else:
        pacing_note = "Leave Starts exactly on season end"

    
    season_end = season_end_dt
    season_days = (season_end - season_start).days
    today = datetime.today()

    month_ticks = []
    current = season_start.replace(day=1)

    # Skip partial first month if season starts mid-month
    if season_start.day > 1:
        current += relativedelta(months=1)

    while current <= season_end:
        month_ticks.append(current)
        current += relativedelta(months=1)

    tick_html = ""
    for dt in month_ticks:
        days_from_start = (dt - season_start).days
        percent = (days_from_start / season_days) * 100

        if percent < 0 or percent > 100:
            continue

        label = dt.strftime("%b")  # e.g. "Jul", "Aug"
        color = "#3b82f6"

        if dt.month == today.month and dt.year == today.year:
            color = "#10b981"

        tick_html += (
            f'<div style="position: absolute; left: {percent:.2f}%; transform: translateX(-50%); '
            f'top: -24px; font-size: 0.60em; color: {color}; text-align: center;" title="{label}">'
            f'{label}</div>\n'
        )


    html_stuff = f"""
                <div style="
                    font-family: 'Georgia', serif;
                    margin: 10px;
                    padding: 10px;
                    background: linear-gradient(to bottom, #fdf6e3, #f5e9c8);
                    border: 2px solid #c2a76d;
                    border-radius: 12px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1), inset 0 0 20px rgba(194,167,109,0.3);
                    position: relative;
                    overflow: hidden;
                ">

                    <!-- <h3 style="font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">📈 Pacing Timeline</h3> -->

                    <!-- Timeline Container -->
                    <div style="border: 1px solid #d1d5db; border-radius: 6px; padding: 15px; background: #f9fafb; display: flex; flex-direction: column; align-items: stretch; gap: 10px;">


                        <!-- Labels Row -->
                        <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #333;">
                            <span style="position: relative; top: -13px;" >🟢 {season_start_fmt}</span>
                            <!-- <span style="position: relative; top: 10px;">📅 {today_fmt}</span> -->
                        <span style="position: relative; top: -13px;">
                            🏁 <i>{format_date_nz(leave_finish_date)} sh</i> – {format_date_nz(season_end_str)}
                            </span>

                        </div>

                        <!-- Blue Line with tick marks -->
                        <div style="position: relative; height: 2px; background: #3b82f6; margin-top: 20px;">
                            {tick_html}
                        </div>

                        <!-- Marker Row -->
                        <div style="position: relative; height: 30px; margin-top: -10px;">
                            <div style="position: absolute; left: calc({surplus_percent}% + 5px); transform: translateX(-50%); text-align: center; font-size: 0.8em;" title="Surplus earned starting {surplus_start_fmt}">
                            <span style="color: green;">▲</span><br><span class="walking-icon1" style="display: inline-block; transform: scaleX(1);">🧍‍♂️</span>

                            </div>
                            <div style="position: absolute; left: {leave_finish_percent}%; transform: translateX(-50%); text-align: center; font-size: 0.8em;" title="Leave starts around {leave_finish_fmt}">
                                </span><span class="bounce_it">▲</span><br>{days_diff} days
                            </div>
                        </div>

                        <!-- Pacing Note -->
                        <p style="font-size: 0.85em; color: #555; margin-top: 5px;">
                            🕒 {pacing_note}
                        </p>
                        
                        <!-- First/Last Shift Preview
                        <p style="font-size: 0.85em; color: #555; margin-top: 5px;">
                            🚀 First shift: {first_shift_fmt} &nbsp;&nbsp;|&nbsp;&nbsp; 🛬 Last shift: {last_shift_fmt}
                        </p> -->
                    </div>
                </div>
                """
    return Markup(html_stuff)

import qrcode
import os
from PIL import Image
from datetime import datetime, timedelta
from urllib.parse import quote
from utils.paths import BASE_DIR, QR_DIR,LOGO_DIR



def QR_code_alarm(emp_id: int,mode: str, message: str = "",
    date: str = None,  # format: 'YYYY-MM-DD'
    duration_minutes: int = 60,
    logo_path: str = "images/TimeDeck.png",
    output_path: str = "images/qrcodes/QR-alarm.png"
    ) -> str:

    logo_path = os.path.join(LOGO_DIR,  "TimeDeck.png")
    output_path = os.path.join(QR_DIR, "QR-alarm.png")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if os.path.exists(output_path):
        os.remove(output_path)
        #print(f"🗑️ Deleted old QR: {output_path}")

    print(f"Logo path: {logo_path}")
    print(f"Output path: {output_path}")
    """
    mode: 'alarm' or 'calendar'
    hour, minutes: time for alarm or event start
    message: label or title
    date: for calendar mode only, format 'YYYY-MM-DD'
    duration_minutes: duration of calendar event
    """
    empconfig = load_json(f"emp_{emp_id}.json")

    # Check and patch missing schedule
    if "schedule" not in empconfig or not empconfig["schedule"]:
        #print(f"⚠️ Patching missing schedule for emp {emp_id}")
        empconfig["schedule"] = {
            "Day": "05:00",
            "Night": "17:00"
        }
        save_json(f"emp_{emp_id}.json", empconfig)

    #print(f"Loaded empconfig for emp_id {emp_id}: {empconfig}")

    roster_entries = load_roster_this_season(emp_id)
    entry = next((x for x in roster_entries if x["date"] == date), None)

    #print(f"Found roster entry for date {date}: {entry}")

    if entry["type_shift"] == "SHIFT" and "cover" in  entry["notes"].lower():
        message = "Shorty : " + entry["notes"]
    else:
        message = entry["type_shift"] + ": " + entry["notes"]
    
    
    #print(f"Generating QR code for emp_id: {emp_id}, mode: {mode}, date: {date}, message: {message}")

    alarm_times = empconfig.get("schedule", {})

    alarm_time = alarm_times.get(entry["shift_type"]) if entry else None
    if not alarm_time:
        raise ValueError("No alarm time found for the given date and shift type.")
    hour, minutes = map(int, alarm_time.split(":"))

    #print(f"Using alarm time: {hour}:{minutes:02}")

    
      # Assuming you have a function to load employee config
    if mode == "alarm":
        # Android alarm intent URI
        intent_uri = (
            "intent:"
            "#Intent;action=android.intent.action.SET_ALARM;"
            f"component=com.android.deskclock/.AlarmClock;"
            f"package=com.android.deskclock;"
            f"S.hour={hour};S.minutes={minutes};S.message={quote(message)};"
            "end"
        )

        qr_data = intent_uri

    elif mode == "calendar":
        if not date:
            raise ValueError("Date is required for calendar mode")

        # Parse date and time
        start_dt = datetime.strptime(f"{date} {hour:02}:{minutes:02}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=12)  # Default to 12-hour event

        start_str = start_dt.strftime("%Y%m%dT%H%M%S")
        end_str = end_dt.strftime("%Y%m%dT%H%M%S")

        calendar_url = (
            "https://www.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote(message)}"
            f"&dates={start_str}/{end_str}"
            f"&details={quote('Created via TimeDeck')}"
            f"&location={quote('TimeDeck')}"
        )
        qr_data = calendar_url  

    else:
        raise ValueError("Invalid mode. Use 'alarm' or 'calendar'.")

    # Generate QR code
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Embed logo
    logo = Image.open(logo_path)
    logo_size = int(qr_img.size[0] * 0.25)
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    pos = ((qr_img.size[0] - logo_size) // 2, (qr_img.size[1] - logo_size) // 2)
    qr_img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)

    # Save image
    qr_img.save(output_path)
    return "Done"