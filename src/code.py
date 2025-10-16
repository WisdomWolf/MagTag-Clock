import rtc # type: ignore
import alarm
import displayio
import terminalio
import time
from adafruit_magtag.magtag import MagTag
from adafruit_display_text import label
from adafruit_display_shapes import roundrect

magtag = MagTag()
border_thickness = 6

TWELVE_HOUR = False

# Graphics
display_width = magtag.graphics.display.width
display_height = magtag.graphics.display.height
magtag.graphics.set_background(0x000000)
magtag.graphics.auto_refresh = True

time_group = displayio.Group()

# Outline
background_rect = roundrect.RoundRect(
    0,
    0,
    display_width,
    display_height,
    10,
    fill=None,
    outline=0xFFFFFF,
    stroke=border_thickness,
)
time_group.append(background_rect)

# Time Background
time_background_rect = roundrect.RoundRect(
    3 * border_thickness,
    display_height // 2 - border_thickness,
    display_width - 6 * border_thickness,
    display_height // 2 - border_thickness,
    10,
    fill=0xFFFFFF,
    outline=None,
    stroke=None,
)
time_group.append(time_background_rect)

# Date Display
date_display = label.Label(terminalio.FONT, text="OMG WTF XD")
date_display.anchor_point = (0.5, 0.0)
date_display.anchored_position = (display_width // 2, 2 * border_thickness)
date_display.scale = 3
date_display.background_color = None

# Time Display
time_display = label.Label(terminalio.FONT, text="XX:XX")
time_display.anchor_point = (0.5, 1.0)
time_display.anchored_position = (
    display_width // 2,
    display_height - 2 * border_thickness,
)
time_display.scale = 5
time_display.color = 0x000000
time_display.background_color = None

time_group.append(date_display)
time_group.append(time_display)

magtag.display.show(time_group)

# Modified from https://learn.adafruit.com/magtag-cat-feeder-clock/getting-the-date-time
def make_time_text(time_struct):
    """Given a time.struct_time, return a string as H:MM or HH:MM, either
    12- or 24-hour style depending on TWELVE_HOUR flag.
    """
    if TWELVE_HOUR:
        postfix = ""
        if time_struct.tm_hour > 12:
            hour_string = str(time_struct.tm_hour - 12)  # 13-23 -> 1-11 (pm)
            postfix = " PM"
        elif time_struct.tm_hour > 0:
            hour_string = str(time_struct.tm_hour)  # 1-12
            postfix = " AM"
            if time_struct.tm_hour == 12:
                postfix = " PM"  # 12 -> 12 (pm)
        else:
            hour_string = "12"  # 0 -> 12 (am)
            postfix = " AM"
        time_string = hour_string + ":{mm:02d}".format(mm=time_struct.tm_min) + postfix
    else:
        time_string = "{hh:02d}:{mm:02d}".format(hh=time_struct.tm_hour, mm=time_struct.tm_min)
    time_display.text = time_string


def make_date_text(time_struct):
    days_of_week = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
    months = (
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    )

    dow = days_of_week[time_struct.tm_wday]
    month = months[time_struct.tm_mon - 1]
    day = time_struct.tm_mday
    year = time_struct.tm_year

    date_string = f"{dow} {month} {day} {year}"

    date_display.text = date_string

now = rtc.RTC().datetime

def update_clock():
    # Don't refresh display until network time is retrieved
    if now.tm_year >= 2025:
        make_time_text(now)
        make_date_text(now)
        time_to_sleep = 60 - now.tm_sec
        alarm.sleep_memory[0] = now.tm_hour % 256
        magtag.display.refresh()
        magtag.exit_and_deep_sleep(time_to_sleep)
    else:
        update_from_network()

def update_from_network(attempt=0):
    try:
        magtag.network.get_local_time()
    except (ValueError, RuntimeError, ConnectionError, OSError):
        attempt += 1
        if attempt:
            time_display.text = f"Try: {attempt}"
            magtag.display.refresh()
            time.sleep(1)
        update_from_network(attempt)
    update_clock()


if not alarm.wake_alarm:
    alarm.sleep_memory[0] = 0
    try:
        time_display.text = "Syncing"
        magtag.display.refresh()
        update_from_network()
    except (ValueError, RuntimeError, ConnectionError, OSError) as e:
        time_display.text = "Error"
        magtag.display.refresh()
        print(e)
        update_clock()
elif alarm.sleep_memory[0] != now.tm_hour:
    try:
        update_from_network()
    except (ValueError, RuntimeError, ConnectionError, OSError) as e:
        print(e)
        update_clock()
else:
    update_clock()
