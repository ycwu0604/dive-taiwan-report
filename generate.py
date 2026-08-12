#!/usr/bin/env python3
"""
潛點台灣 Dive Taiwan — 靜態報告產生器
從 CWA 鄉鎮沿海 + Open-Meteo Marine + Open-Meteo Weather 抓資料，產生一份 HTML 報告。
"""

import json
import os
import platform
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

# ─── HTTP fetcher: curl.exe fallback for OA proxy SSL ───

def _curl_available() -> bool:
    return platform.system() == "Windows" and shutil.which("curl.exe") is not None

USE_CURL = _curl_available()

def fetch_text(url: str, timeout: int = 15) -> str:
    if USE_CURL:
        try:
            r = subprocess.run(
                ["curl.exe", "-sS", "--ssl-no-revoke", "-k", "--max-time", str(timeout), url],
                capture_output=True, timeout=timeout + 5)
            if r.returncode == 0 and r.stdout:
                return r.stdout.decode("utf-8", errors="replace")
            if r.stderr:
                err = r.stderr.decode("utf-8", errors="replace").strip()
                if err:
                    print(f"[WARN] curl stderr: {url} → {err[:120]}")
        except Exception as e:
            print(f"[WARN] curl exception: {url} → {e}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DiveTaiwan/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[WARN] urllib failed: {url} → {e}")
    return ""

def fetch_json(url: str, timeout: int = 20) -> dict:
    raw = fetch_text(url, timeout)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON parse failed: {url} → {e}")
        return {}

# ─── 15 潛點定義 ───

DIVES = [
    # ── 東北角 ──
    # ── 東北角 ──
    {
        "id": "chaojing",
        "name": "潮境",
        "region": "ne",
        "county": "基隆",
        "facing": "NE",
        "terrain": "開放海岸",
        "shelter": 1.0,   # no shelter factor
        "lat": 25.14, "lon": 121.80,
        "off_lat": 25.15, "off_lon": 121.80,
        "sid": "1000204C01",   # 頭城站 (closest)
        "depth": "5-25m",
        "level": "中級",
        "feature": "保育區·海扇·軟珊瑚",
    },
    {
        "id": "batcave",
        "name": "蝙蝠洞",
        "region": "ne",
        "county": "新北瑞芳",
        "facing": "NE",
        "terrain": "開放海岸",
        "shelter": 1.0,
        "lat": 25.127, "lon": 121.831,
        "off_lat": 25.13, "off_lon": 121.84,
        "sid": "1000204C01",
        "depth": "5-30m",
        "level": "初級",
        "feature": "一線天峽谷·微距天堂",
    },
    {
        "id": "longdong",
        "name": "龍洞",
        "region": "ne",
        "county": "新北貢寮",
        "facing": "E",
        "terrain": "灣內",
        "shelter": 0.6,   # bay reduces wave height ~40%
        "lat": 25.12, "lon": 121.92,
        "off_lat": 25.12, "off_lon": 121.93,
        "sid": "1000204C01",
        "depth": "5-30m",
        "level": "初~進階",
        "feature": "灣內入門·灣外峭壁",
    },
    {
        "id": "meiyan",
        "name": "美艷山",
        "region": "ne",
        "county": "新北貢寮",
        "facing": "E",
        "terrain": "內灣",
        "shelter": 0.7,
        "lat": 25.072, "lon": 121.923,
        "off_lat": 25.07, "off_lon": 121.93,
        "sid": "1000204C01",
        "depth": "3-15m",
        "level": "中級",
        "feature": "內灣擋浪·沙底岩礁·海蛞蝓",
    },
    # ── 墾丁 ──
    {
        "id": "houbihu",
        "name": "出水口(後壁湖)",
        "region": "kt",
        "county": "屏東恆春",
        "facing": "S",
        "terrain": "灣內",
        "shelter": 0.5,   # 後壁湖灣內遮蔽高
        "lat": 21.94, "lon": 120.74,
        "off_lat": 21.93, "off_lon": 120.72,
        "sid": "1001304C01",   # 恆春鎮
        "depth": "3-20m",
        "level": "初級",
        "feature": "保護區·出水口魚群·微距",
    },
    {
        "id": "sailrock",
        "name": "船帆石",
        "region": "kt",
        "county": "屏東恆春",
        "facing": "S",
        "terrain": "開放海岸",
        "shelter": 0.8,   # 珊瑚礁部分遮擋
        "lat": 21.93, "lon": 120.78,
        "off_lat": 21.91, "off_lon": 120.77,
        "sid": "1001304C01",   # 恆春鎮
        "depth": "5-25m",
        "level": "初~中級",
        "feature": "珊瑚礁·海龜·初潛熱點",
    },
    {
        "id": "hejie",
        "name": "合界",
        "region": "kt",
        "county": "屏東恆春",
        "facing": "W",
        "terrain": "開放海岸",
        "shelter": 1.0,   # 完全開放·放流潛
        "lat": 21.97, "lon": 120.74,
        "off_lat": 21.97, "off_lon": 120.70,
        "sid": "1001304C01",   # 恆春鎮
        "depth": "10-35m",
        "level": "進階",
        "feature": "放流潛·峽谷地形·大物",
    },
    # ── 綠島 ──
    {
        "id": "chaikou",
        "name": "柴口",
        "region": "gi",
        "county": "臺東綠島",
        "facing": "NW",
        "terrain": "灣內",
        "shelter": 0.6,   # 北側灣內·有礁遮擋
        "lat": 22.675, "lon": 121.467,
        "off_lat": 22.68, "off_lon": 121.45,
        "sid": "1001411C01",   # 綠島鄉_北方
        "depth": "3-18m",
        "level": "初級",
        "feature": "灣內入門·軟珊瑚·魚群",
    },
    {
        "id": "yixiantian",
        "name": "一線天",
        "region": "gi",
        "county": "臺東綠島",
        "facing": "NW",
        "terrain": "船潛",
        "shelter": 0.8,   # 北側有部分礁遮
        "lat": 22.655, "lon": 121.483,
        "off_lat": 22.65, "off_lon": 121.49,
        "sid": "1001411C01",   # 綠島鄉_北方
        "depth": "10-30m",
        "level": "中級",
        "feature": "峽谷地形·海扇·放流",
    },
    {
        "id": "steelreef",
        "name": "鋼鐵礁",
        "region": "gi",
        "county": "臺東綠島",
        "facing": "SE",
        "terrain": "船潛",
        "shelter": 1.0,   # 完全開放
        "lat": 22.645, "lon": 121.495,
        "off_lat": 22.64, "off_lon": 121.50,
        "sid": "1001411C02",   # 綠島鄉_南方
        "depth": "20-40m",
        "level": "進階",
        "feature": "人工魚礁·大物·深潛",
    },
    {
        "id": "ziping",
        "name": "紫坪",
        "region": "gi",
        "county": "臺東綠島",
        "facing": "SW",
        "terrain": "船潛",
        "shelter": 0.5,   # 灣內遮蔽高
        "lat": 22.648, "lon": 121.478,
        "off_lat": 22.65, "off_lon": 121.48,
        "sid": "1001411C02",   # 綠島鄉_南方
        "depth": "5-20m",
        "level": "初級",
        "feature": "灣內沙底·微距·夜潛",
    },
    {
        "id": "jizaijei",
        "name": "雞仔礁",
        "region": "gi",
        "county": "臺東綠島",
        "facing": "E",
        "terrain": "船潛",
        "shelter": 1.0,   # 東側開放
        "lat": 22.665, "lon": 121.498,
        "off_lat": 22.67, "off_lon": 121.50,
        "sid": "1001411C01",   # 綠島鄉_北方
        "depth": "15-35m",
        "level": "中~進階",
        "feature": "斷崖地形·海扇·大物",
    },
    # ── 蘭嶼 ──
    {
        "id": "badaiwan",
        "name": "八代灣",
        "region": "ly",
        "county": "臺東蘭嶼",
        "facing": "SW",
        "terrain": "船潛",
        "shelter": 0.7,   # 灣內有遮擋
        "lat": 22.04, "lon": 121.55,
        "off_lat": 22.03, "off_lon": 121.54,
        "sid": "1001416C02",   # 蘭嶼鄉_南方
        "depth": "15-40m",
        "level": "中~進階",
        "feature": "沈船·海扇森林·大物",
    },
    {
        "id": "yeyou",
        "name": "椰油斷層",
        "region": "ly",
        "county": "臺東蘭嶼",
        "facing": "NW",
        "terrain": "船潛",
        "shelter": 1.0,   # 斷層壁開放
        "lat": 22.06, "lon": 121.54,
        "off_lat": 22.07, "off_lon": 121.53,
        "sid": "1001416C01",   # 蘭嶼鄉_北方
        "depth": "10-40m",
        "level": "進階",
        "feature": "斷層壁·海扇·深潛",
    },
    {
        "id": "shuangshiyan",
        "name": "雙獅岩",
        "region": "ly",
        "county": "臺東蘭嶼",
        "facing": "NE",
        "terrain": "船潛",
        "shelter": 1.0,   # 東北側完全開放
        "lat": 22.07, "lon": 121.58,
        "off_lat": 22.08, "off_lon": 121.59,
        "sid": "1001416C01",   # 蘭嶼鄉_北方
        "depth": "15-35m",
        "level": "中~進階",
        "feature": "巨岩地形·珊瑚花園·放流",
    },
]

TZ = timezone(timedelta(hours=8))

# ─── CWA 3hr HTML parser (shared with surf report) ───

def _extract_ws_ms(cell_html: str) -> float:
    m = re.search(r'<span\s+class="WS[^"]*">([\d.]+)</span>', cell_html, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    stripped = re.sub(r"<[^>]+>", "", cell_html).strip()
    try:
        return float(stripped)
    except (ValueError, TypeError):
        return 0.0

def parse_cwa_3hr(html: str) -> list[dict]:
    rows = re.split(r"<tr[^>]*>", html, flags=re.IGNORECASE)[1:]
    results = []
    for row in rows:
        td_matches = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row, re.IGNORECASE)
        if len(td_matches) < 10:
            continue

        has_date_row = len(td_matches) >= 11 and bool(re.search(r'class="WS', td_matches[2], re.IGNORECASE))
        offset = 1 if has_date_row else 0

        cells = [re.sub(r"<[^>]+>", "", m).strip() for m in td_matches]
        date_str = cells[0] if has_date_row else ""
        time_str = cells[offset]
        wind_speed_html = td_matches[offset + 1]
        wind_force = cells[offset + 2]
        wind_dir = cells[offset + 3]
        wave_height_str = cells[offset + 4]
        wave_dir = cells[offset + 5]
        wave_period_str = cells[offset + 6]

        yr = datetime.now(TZ).year
        if has_date_row:
            date_part = re.match(r"(\d{1,2}/\d{1,2})", date_str)
            if date_part:
                mm = date_part.group(1).split("/")
                iso = f"{yr}-{mm[0].zfill(2)}-{mm[1].zfill(2)}T{time_str.strip()}:00+08:00"
            else:
                iso = f"{date_str} {time_str}"
        else:
            if results:
                prev_date = results[-1]["time"][:10]
                iso = f"{prev_date}T{time_str.strip()}:00+08:00"
            else:
                continue

        try:
            wh = float(wave_height_str) if wave_height_str else 0.0
        except ValueError:
            wh = 0.0
        try:
            wp = float(wave_period_str) if wave_period_str else 0.0
        except ValueError:
            wp = 0.0
        ws = _extract_ws_ms(wind_speed_html)

        results.append({
            "time": iso,
            "wave_height": wh,
            "wave_period": wp,
            "wave_dir": wave_dir,
            "wind_speed": ws,
            "wind_dir": wind_dir,
        })
    return results

# ─── CWA Tide HTML parser ───

def parse_cwa_tide(html: str, day_offset: int = 1) -> list[dict]:
    all_cells = re.findall(r"<(t[dh])[^>]*>([\s\S]*?)</\1>", html, re.IGNORECASE)
    tides = []
    d = datetime.now(TZ) + timedelta(days=day_offset - 1)
    current_date = d.strftime("%Y-%m-%d")

    for i, (tag, raw) in enumerate(all_cells):
        stripped = re.sub(r"<[^>]+>", "", raw).strip()
        if stripped in ("滿潮", "乾潮"):
            ttype = stripped
            ttime = ""
            height = 0
            for j in range(i + 1, min(i + 5, len(all_cells))):
                next_stripped = re.sub(r"<[^>]+>", "", all_cells[j][1]).strip()
                if not ttime and re.match(r"\d{1,2}:\d{2}", next_stripped):
                    ttime = next_stripped
                elif ttime:
                    try:
                        height = float(next_stripped)
                        break
                    except ValueError:
                        continue
            if ttime:
                tides.append({"type": ttype, "time": ttime, "date": current_date, "height": height})
    return tides

# ─── Open-Meteo Marine ───

def fetch_open_meteo_marine(lat: float, lon: float) -> list[dict]:
    url = (f"https://marine-api.open-meteo.com/v1/marine?"
           f"latitude={lat}&longitude={lon}"
           f"&hourly=wave_height,wave_period,wave_direction"
           f"&timezone=Asia/Taipei&forecast_days=7")
    data = fetch_json(url)
    if not data or "hourly" not in data:
        return []
    h = data["hourly"]
    results = []
    for i, t in enumerate(h.get("time", [])):
        results.append({
            "time": t,
            "wave_height": h["wave_height"][i],
            "wave_period": h["wave_period"][i],
            "wave_direction": h["wave_direction"][i],
        })
    return results

# ─── Open-Meteo Weather (rain, temp, weather_code) ───

def fetch_open_meteo_weather(lat: float, lon: float) -> tuple[list[dict], dict[str, dict]]:
    """Returns (hourly_weather, sun_dict). sun_dict = {'2026-08-12': {'rise': '05:24', 'set': '18:30'}, ...}"""
    url = (f"https://api.open-meteo.com/v1/forecast?"
           f"latitude={lat}&longitude={lon}"
           f"&hourly=temperature_2m,precipitation,weather_code"
           f"&daily=sunrise,sunset"
           f"&timezone=Asia/Taipei&forecast_days=7")
    data = fetch_json(url)
    if not data or "hourly" not in data:
        return [], {}
    h = data["hourly"]
    results = []
    for i, t in enumerate(h.get("time", [])):
        results.append({
            "time": t,
            "temp": h["temperature_2m"][i],
            "rain": h["precipitation"][i],
            "weather_code": h["weather_code"][i],
        })
    # Parse sunrise/sunset
    sun_dict: dict[str, dict] = {}
    if "daily" in data:
        d = data["daily"]
        for i, date in enumerate(d.get("time", [])):
            rise = d["sunrise"][i][11:16] if i < len(d.get("sunrise", [])) else ""
            set_ = d["sunset"][i][11:16] if i < len(d.get("sunset", [])) else ""
            sun_dict[date] = {"rise": rise, "set": set_}
    return results, sun_dict

WMO_DESC = {
    0: "晴", 1: "晴", 2: "多雲", 3: "陰",
    45: "霧", 48: "霧",
    51: "小雨", 53: "小雨", 55: "中雨",
    56: "凍雨", 57: "凍雨",
    61: "陣雨", 63: "陣雨", 65: "大雨",
    66: "凍雨", 67: "凍雨",
    71: "小雪", 73: "小雪", 75: "大雪",
    77: "雪粒",
    80: "陣雨", 81: "陣雨", 82: "暴雨",
    85: "陣雪", 86: "大雪",
    95: "雷雨", 96: "冰雹雷雨", 99: "冰雹雷雨",
}

def wmo_to_tw(code) -> str:
    if code is None:
        return ""
    return WMO_DESC.get(int(code), "")

def is_bad_weather(code) -> bool:
    """Return True if weather_code indicates rain/storm."""
    if code is None:
        return False
    c = int(code)
    return c >= 51  # any rain or worse

# ─── Day grouping ───

WEEKDAY_TW = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

def group_by_day(rows: list[dict]) -> dict[str, list[dict]]:
    days: dict[str, list[dict]] = {}
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["time"])
            ymd = dt.strftime("%Y-%m-%d")
        except Exception:
            ymd = r["time"][:10] if r.get("time") else ""
        if ymd:
            days.setdefault(ymd, []).append(r)
    return days

def day_summary(cwa_rows, om_rows, weather_rows, shelter_factor=1.0) -> dict:
    wh_all = [r["wave_height"] for r in cwa_rows if r["wave_height"]] + \
             [r["wave_height"] for r in om_rows if r.get("wave_height") is not None]
    wp_all = [r["wave_period"] for r in cwa_rows if r["wave_period"]] + \
             [r["wave_period"] for r in om_rows if r.get("wave_period") is not None]
    ws_all = [r["wind_speed"] for r in cwa_rows if r["wind_speed"]]

    max_wh_raw = max(wh_all) if wh_all else 0
    max_wh = max_wh_raw * shelter_factor  # shelter adjustment
    avg_wp = sum(wp_all) / len(wp_all) if wp_all else 0
    max_ws = max(ws_all) if ws_all else 0

    # Weather summary
    rain_total = sum(r.get("rain", 0) or 0 for r in weather_rows)
    avg_temp = None
    temps = [r["temp"] for r in weather_rows if r.get("temp") is not None]
    if temps:
        avg_temp = round(sum(temps) / len(temps), 1)

    # Dominant weather
    wc_counts = {}
    for r in weather_rows:
        wc = r.get("weather_code")
        if wc is not None:
            wc_counts[wc] = wc_counts.get(wc, 0) + 1
    dom_wc = max(wc_counts, key=wc_counts.get) if wc_counts else None
    weather_desc = wmo_to_tw(dom_wc) if dom_wc is not None else ""

    # Visibility estimate
    vis = estimate_visibility(max_wh_raw, rain_total, max_ws)

    wdir = cwa_rows[0]["wave_dir"] if cwa_rows else ""
    om_dirs = [r["wave_direction"] for r in om_rows if r.get("wave_direction") is not None]
    om_dir = om_dirs[len(om_dirs)//2] if om_dirs else None

    return {
        "wave_height_max": round(max_wh, 1),
        "wave_height_max_raw": round(max_wh_raw, 1),
        "wave_period_avg": round(avg_wp, 1),
        "wind_speed_max": round(max_ws, 1),
        "wind_speed_max_kt": round(max_ws * 1.944, 0),
        "wave_dir": wdir,
        "wave_dir_deg": om_dir,
        "rain_total": round(rain_total, 1),
        "avg_temp": avg_temp,
        "weather": weather_desc,
        "weather_code": dom_wc,
        "visibility": vis,
    }

def estimate_visibility(wave_height, rain_24h, wind_speed) -> str:
    """Estimate visibility based on indirect factors."""
    if rain_24h > 30:
        return "差"
    if rain_24h > 10 and wave_height > 1.5:
        return "差"
    if wave_height > 2.5:
        return "差"
    if rain_24h > 5 or wave_height > 1.5:
        return "普通"
    if rain_24h <= 2 and wave_height < 0.8:
        return "佳"
    return "普通"

def dive_rating(wh, ws_kt, weather_code, visibility) -> str:
    """Return dive suitability rating. Lower wave + wind = better for diving."""
    is_rain = is_bad_weather(weather_code) if weather_code is not None else False
    is_storm = weather_code is not None and int(weather_code) >= 95

    if is_storm:
        return "🚫 雷雨危險"
    if wh >= 2.5 or ws_kt >= 25:
        return "🔴 不適合潛水"
    if wh >= 2.0 or ws_kt >= 20:
        return "🟠 建議取消"
    if wh >= 1.5 or ws_kt >= 15 or is_rain:
        return "🟡 條件普通"
    if ws_kt >= 10:
        return "🟢 微風適潛"
    if wh < 1.0 and ws_kt < 10 and not is_rain:
        return "🟢 適合潛水"
    return "🟢 適合潛水"

def _rating_rank(rating: str) -> int:
    if rating.startswith("🟢") and "適合潛水" in rating and "微風" not in rating:
        return 100
    if rating.startswith("🟢") and "微風" in rating:
        return 150
    if rating.startswith("🟡"):
        return 200
    if rating.startswith("🟠"):
        return 300
    if rating.startswith("🔴"):
        return 500
    if rating.startswith("🚫"):
        return 900
    return 800

# ─── Generate report ───

def generate_report() -> str:
    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    today_label = f"{now.month}/{now.day} ({WEEKDAY_TW[now.weekday()]})"

    # Fetch CWA data (group by SID to avoid duplicate requests)
    unique_sids = list({d["sid"] for d in DIVES})
    cwa_days_by_sid: dict[str, dict] = {}
    tide_by_sid: dict[str, dict[str, list[dict]]] = {}

    for sid in unique_sids:
        cwa_html = fetch_text(f"https://www.cwa.gov.tw/V8/C/M/TownCoastal/MOD/3hr/{sid}.html")
        cwa_rows = parse_cwa_3hr(cwa_html)
        cwa_days_by_sid[sid] = group_by_day(cwa_rows)

        tide_all = []
        for d in range(1, 6):
            tide_html = fetch_text(
                f"https://www.cwa.gov.tw/V8/C/M/TownCoastal/MOD/Tide/{sid}_Day{d}.html")
            tide_all.extend(parse_cwa_tide(tide_html, day_offset=d))
        tide_by_sid[sid] = {}
        for t in tide_all:
            tide_by_sid[sid].setdefault(t["date"], []).append(t)

    all_dives_data = []

    for dive in DIVES:
        # Open-Meteo Marine (per-dive coordinates)
        om_rows = fetch_open_meteo_marine(dive["off_lat"], dive["off_lon"])
        om_days = group_by_day(om_rows)

        # Open-Meteo Weather (per-dive coordinates) + sunrise/sunset
        wx_rows, sun_dict = fetch_open_meteo_weather(dive["lat"], dive["lon"])
        wx_days = group_by_day(wx_rows)

        sid = dive["sid"]
        cwa_days = cwa_days_by_sid.get(sid, {})
        tide_by_date = tide_by_sid.get(sid, {})

        # Build 4-day forecast
        forecast = []
        for i in range(4):
            d = now + timedelta(days=i)
            ymd = d.strftime("%Y-%m-%d")
            cwa = cwa_days.get(ymd, [])
            om = om_days.get(ymd, [])
            wx = wx_days.get(ymd, [])
            tide = tide_by_date.get(ymd, [])

            summ = day_summary(cwa, om, wx, dive["shelter"])

            # Day-level weather: take noon value or most common
            noon_wx = None
            for r in wx:
                try:
                    hr = datetime.fromisoformat(r["time"]).hour
                except Exception:
                    continue
                if hr == 12:
                    noon_wx = r
                    break
            day_weather_code = noon_wx.get("weather_code") if noon_wx else summ["weather_code"]

            rating = dive_rating(
                summ["wave_height_max"],
                summ["wind_speed_max_kt"],
                day_weather_code,
                summ["visibility"],
            )

            # 3-hourly detail
            detail = []
            if cwa:
                for r in cwa:
                    # Apply shelter to wave height for detail too
                    wh_sheltered = round(r["wave_height"] * dive["shelter"], 1)
                    detail.append({
                        "time": r["time"][11:16] if len(r["time"]) > 16 else r["time"],
                        "wave_height": wh_sheltered,
                        "wave_period": r["wave_period"],
                        "wave_dir": r["wave_dir"],
                        "wind_speed_kt": round(r["wind_speed"] * 1.944, 0),
                        "wind_dir": r["wind_dir"],
                    })
            elif om:
                sampled = [r for idx, r in enumerate(om) if idx % 3 == 0]
                for r in sampled:
                    if r.get("wave_height") is None:
                        continue
                    wh_sheltered = round(r["wave_height"] * dive["shelter"], 1)
                    detail.append({
                        "time": r["time"][11:16] if len(r["time"]) > 16 else r["time"],
                        "wave_height": wh_sheltered,
                        "wave_period": r["wave_period"],
                        "wave_dir": deg_to_compass(r.get("wave_direction")),
                        "wind_speed_kt": None,
                        "wind_dir": "",
                    })

            # Weather detail (hourly → pick every 3hr matching detail)
            weather_detail = {}
            for r in wx:
                try:
                    hr = datetime.fromisoformat(r["time"]).hour
                except Exception:
                    continue
                if hr % 3 == 0:
                    time_key = r["time"][11:16]
                    weather_detail[time_key] = {
                        "weather": wmo_to_tw(r.get("weather_code")),
                        "rain": r.get("rain", 0) or 0,
                    }

            forecast.append({
                "date": ymd,
                "weekday": WEEKDAY_TW[d.weekday()],
                "short": f"{d.month}/{d.day}",
                "summary": summ,
                "rating": rating,
                "tide": tide,
                "detail": detail,
                "weather_detail": weather_detail,
                "sunrise": sun_dict.get(ymd, {}).get("rise", ""),
                "sunset": sun_dict.get(ymd, {}).get("set", ""),
            })

        # Best day = most diveable (lowest rating rank, then lowest wave)
        def _day_dive_score(f):
            return (_rating_rank(f["rating"]), f["summary"]["wave_height_max"])

        best_day = min(forecast, key=_day_dive_score) if forecast else None

        all_dives_data.append({
            "dive": dive,
            "forecast": forecast,
            "best_day": best_day,
        })

    # Build ranking
    all_rankings = []
    for sd in all_dives_data:
        if sd["best_day"]:
            rating = sd["best_day"]["rating"]
            all_rankings.append({
                "name": sd["dive"]["name"],
                "county": sd["dive"]["county"],
                "terrain": sd["dive"]["terrain"],
                "best_date": sd["best_day"]["short"],
                "best_weekday": sd["best_day"]["weekday"],
                "wave_height": sd["best_day"]["summary"]["wave_height_max"],
                "wind_kt": int(sd["best_day"]["summary"]["wind_speed_max_kt"]),
                "weather": sd["best_day"]["summary"]["weather"],
                "visibility": sd["best_day"]["summary"]["visibility"],
                "rating": rating,
                "_rank": _rating_rank(rating),
            })

    all_rankings.sort(key=lambda r: (r["_rank"], r["wave_height"]))
    diveable = [r for r in all_rankings if r["_rank"] < 500]
    ranking_source = diveable if diveable else all_rankings
    ranking = []
    for r in ranking_source[:4]:
        ranking.append({k: v for k, v in r.items() if k != "_rank"})

    html = render_html(now, today_label, ranking, all_dives_data)
    return html


def deg_to_compass(deg) -> str:
    if deg is None:
        return ""
    try:
        d = float(deg)
    except (TypeError, ValueError):
        return str(deg)
    dirs = ["北", "東北", "東", "東南", "南", "西南", "西", "西北"]
    return dirs[round(d / 45) % 8]


def vis_class(vis: str) -> str:
    if vis == "佳":
        return "vis-good"
    if vis == "差":
        return "vis-bad"
    return "vis-ok"


def wave_color_class(wh: float) -> str:
    if not wh or wh <= 0:
        return "wh-c0"
    if wh < 0.8:
        return "wh-c1"
    if wh < 1.5:
        return "wh-c2"
    if wh < 2.5:
        return "wh-c3"
    return "wh-c4"


def render_html(now, today_label, ranking, all_dives_data) -> str:
    generated = now.strftime("%Y-%m-%d %H:%M")

    ranking_rows = ""
    for i, r in enumerate(ranking, 1):
        star = "⭐" if i <= 2 else ""
        ranking_rows += f"""
        <tr class="rank-row rank-{i}">
          <td class="rank-num">{star}{i}</td>
          <td class="rank-name">{escape(r['name'])}<span class="rank-county">{escape(r['county'])}</span></td>
          <td class="rank-terrain">{escape(r['terrain'])}</td>
          <td class="rank-date">{escape(r['best_date'])} {escape(r['best_weekday'])}</td>
          <td class="rank-wh">{r['wave_height']}m</td>
          <td class="rank-ws">{r['wind_kt']}kt</td>
          <td class="rank-weather">{escape(r['weather'])}</td>
          <td class="rank-vis {vis_class(r['visibility'])}">能見度{escape(r['visibility'])}</td>
          <td class="rank-rating">{r['rating']}</td>
        </tr>"""

    REGION_LABELS = {"ne": "🌊 東北角", "kt": "🌴 墾丁", "gi": "🏝️ 綠島", "ly": "🌋 蘭嶼"}
    current_region = ""

    dive_cards = ""
    for sd in all_dives_data:
        dive = sd["dive"]
        fc = sd["forecast"]
        best = sd["best_day"]

        # Region separator
        if dive.get("region") != current_region:
            current_region = dive.get("region", "")
            label = REGION_LABELS.get(current_region, current_region)
            dive_cards += f'<div class="region-sep">{label}</div>'

        best_info = ""
        if best:
            best_info = (f'<span class="spot-best">最佳日 {best["short"]} {best["weekday"]} '
                         f'· {best["summary"]["wave_height_max"]}m · {best["rating"]}</span>')

        day_tables = ""
        for day in fc:
            summ = day["summary"]

            tide_html = ""
            for t in day["tide"]:
                tc = "tide-high" if t["type"] == "滿潮" else "tide-low"
                arrow = "▲" if t["type"] == "滿潮" else "▼"
                tide_html += f'<span class="tide-item {tc}">{arrow} {escape(t["type"])} {escape(t["time"])}<small class="tide-h">{t["height"]}cm</small></span>'

            detail_rows = ""
            for dr in day["detail"]:
                ws_str = f'{dr["wind_speed_kt"]:.0f}kt' if dr["wind_speed_kt"] is not None else "—"
                wh_class = wave_color_class(dr["wave_height"])
                # Get weather for this time slot
                wd = day.get("weather_detail", {})
                w_info = wd.get(dr["time"], {})
                w_text = w_info.get("weather", "")
                rain_val = w_info.get("rain", 0) or 0
                rain_str = f'<span class="d-rain">{rain_val:.0f}mm</span>' if rain_val > 0 else ""
                weather_cell = f'<span class="d-weather">{escape(w_text)}</span>{rain_str}' if w_text else "—"

                detail_rows += f"""
                <tr>
                  <td class="d-time">{escape(dr['time'])}</td>
                  <td class="d-wh-cell"><div class="wh-mini {wh_class}"></div><span class="d-wh-num">{dr['wave_height']}m</span></td>
                  <td class="d-wp">{dr['wave_period']}s</td>
                  <td class="d-dir">{escape(dr['wave_dir'])}</td>
                  <td class="d-ws"><span class="d-ws-num">{ws_str}</span> <span class="d-ws-dir">{escape(dr['wind_dir'])}</span></td>
                  <td class="d-weather-cell">{weather_cell}</td>
                </tr>"""

            day_tables += f"""
          <div class="day-block">
            <div class="day-header">
              <span class="day-date">{escape(day['weekday'])} {escape(day['short'])}</span>
              <span class="day-sun">☀️ {escape(day['sunrise'])} 🌙 {escape(day['sunset'])}</span>
              <span class="day-summary">
                {summ['wave_height_max']}m · {summ['wind_speed_max_kt']:.0f}kt · {escape(summ['weather'])} · {escape(summ['wave_dir'])}
              </span>
              <span class="day-vis {vis_class(summ['visibility'])}">能見度{escape(summ['visibility'])}</span>
              <span class="day-rating">{day['rating']}</span>
            </div>
            {"<div class='tide-strip'>" + tide_html + "</div>" if tide_html else ""}
            <table class="detail-table">
              <thead><tr><th>時刻</th><th>浪高</th><th>週期</th><th>浪向</th><th>風速·風向</th><th>天氣</th></tr></thead>
              <tbody>{detail_rows}</tbody>
            </table>
          </div>"""

        terrain_badge = f'<span class="terrain-badge">{escape(dive["terrain"])}</span>'
        level_badge = f'<span class="level-badge">{escape(dive["level"])}</span>'

        dive_cards += f"""
      <div class="spot-card region-{dive['region']}" id="{dive['id']}">
        <div class="spot-head" onclick="toggleSpot('{dive['id']}')" role="button" tabindex="0">
          <h2 class="spot-name">🤿 {escape(dive['name'])}</h2>
          <span class="spot-badge">{escape(dive['facing'])}</span>
          {terrain_badge} {level_badge}
          <span class="spot-county">{escape(dive['county'])}</span>
          <span class="spot-toggle" id="toggle-{dive['id']}">▶</span>
        </div>
        <div class="spot-summary-row">
          {best_info}
          <span class="spot-today-wh">{fc[0]['summary']['wave_height_max']}m</span>
          <span class="spot-today-ws">{fc[0]['summary']['wind_speed_max_kt']:.0f}kt</span>
          <span class="spot-today-weather">{escape(fc[0]['summary']['weather'])}</span>
          <span class="spot-today-vis {vis_class(fc[0]['summary']['visibility'])}">能見度{escape(fc[0]['summary']['visibility'])}</span>
          <span class="spot-today-rating">{fc[0]['rating']}</span>
        </div>
        <div class="spot-forecast" id="fc-{dive['id']}">{day_tables}</div>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>潛點台灣 · {escape(today_label)}</title>
<style>
:root {{
  --bg: #051520; --card: #0c2636; --card2: #133a4e;
  --text: #e0f0ff; --dim: #6ba3c7; --accent: #00e5ff;
  --wave1: #26c6da; --wave2: #0288d1; --wave3: #ff9800; --wave4: #ff4081;
  --tide-hi: #26a69a; --tide-lo: #4dd0e1;
  --vis-good: #4caf50; --vis-ok: #ff9800; --vis-bad: #f44336;
  --sand: #bcaaa4; --border: #1a4a5e; --radius: 8px;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: "Noto Sans TC","Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); line-height:1.5; padding:12px; max-width:960px; margin:0 auto; }}
a {{ color:var(--accent); }}

.hero {{ text-align:center; padding:24px 0 16px; }}
.hero h1 {{ font-size:clamp(1.8rem,5vw,2.6rem); font-weight:700; background:linear-gradient(120deg,#fff 30%,var(--accent) 80%); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }}
.hero .sub {{ color:var(--dim); font-size:.9rem; margin-top:4px; }}
.hero .meta {{ color:var(--dim); font-size:.75rem; margin-top:8px; }}

/* Ranking */
.ranking {{ margin:20px 0; }}
.ranking h2 {{ font-size:1.2rem; margin-bottom:10px; }}
.rank-table {{ width:100%; border-collapse:collapse; font-size:.8rem; }}
.rank-table th {{ text-align:left; color:var(--dim); padding:6px 6px; border-bottom:1px solid var(--border); font-weight:400; letter-spacing:.04em; }}
.rank-table td {{ padding:7px 6px; border-bottom:1px solid rgba(255,255,255,.05); }}
.rank-num {{ font-weight:700; min-width:28px; }}
.rank-name {{ font-weight:600; }}
.rank-county {{ color:var(--dim); font-weight:400; margin-left:4px; font-size:.75rem; }}
.rank-1 .rank-num, .rank-2 .rank-num {{ color:var(--sand); }}
.rank-wh {{ font-weight:700; font-variant-numeric:tabular-nums; }}
.rank-vis {{ font-weight:600; font-size:.78rem; }}
.vis-good {{ color:var(--vis-good); }}
.vis-ok {{ color:var(--vis-ok); }}
.vis-bad {{ color:var(--vis-bad); }}
.rank-rating {{ white-space:nowrap; }}

/* Dive cards */
.spot-card {{ background:var(--card); border-radius:var(--radius); margin:8px 0; border:1px solid var(--border); overflow:hidden; }}
.spot-card.region-ne {{ background:rgba(10,30,60,.55); border-color:rgba(60,140,220,.25); }}
.spot-card.region-kt {{ background:rgba(50,20,10,.45); border-color:rgba(220,140,60,.25); }}
.spot-card.region-gi {{ background:rgba(10,40,30,.5); border-color:rgba(0,200,120,.25); }}
.spot-card.region-ly {{ background:rgba(40,15,15,.5); border-color:rgba(200,80,80,.25); }}
.spot-card.region-ne .spot-head:hover {{ background:rgba(60,140,220,.08); }}
.spot-card.region-kt .spot-head:hover {{ background:rgba(220,140,60,.08); }}
.spot-card.region-gi .spot-head:hover {{ background:rgba(0,200,120,.08); }}
.spot-card.region-ly .spot-head:hover {{ background:rgba(200,80,80,.08); }}
.region-sep {{ font-size:1.1rem; font-weight:700; padding:14px 0 4px; color:var(--accent); letter-spacing:1px; }}
.spot-head {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; padding:12px 14px; cursor:pointer; user-select:none; }}
.spot-head:hover {{ background:rgba(0,229,255,.04); }}
.spot-name {{ font-size:1.3rem; font-weight:700; }}
.spot-badge {{ background:rgba(0,229,255,.15); color:var(--accent); padding:2px 8px; border-radius:12px; font-size:.72rem; font-weight:600; }}
.terrain-badge {{ background:rgba(38,166,154,.15); color:var(--tide-hi); padding:2px 8px; border-radius:12px; font-size:.72rem; font-weight:600; }}
.level-badge {{ background:rgba(188,170,164,.12); color:var(--sand); padding:2px 8px; border-radius:12px; font-size:.72rem; font-weight:600; }}
.spot-county {{ color:var(--dim); font-size:.82rem; }}
.spot-toggle {{ margin-left:auto; color:var(--dim); font-size:.8rem; transition:transform .2s; }}
.spot-toggle.open {{ transform:rotate(90deg); }}
.spot-summary-row {{ display:flex; align-items:center; gap:10px; padding:0 14px 10px; flex-wrap:wrap; }}
.spot-best {{ color:var(--sand); font-size:.82rem; }}
.spot-today-wh {{ font-weight:800; font-size:1.05rem; color:#fff; }}
.spot-today-ws {{ color:var(--dim); font-size:.82rem; }}
.spot-today-weather {{ font-size:.82rem; }}
.spot-today-vis {{ font-weight:600; font-size:.8rem; }}
.spot-today-rating {{ font-weight:600; }}
.spot-forecast {{ display:none; padding:0 10px 10px; }}
.spot-forecast.open {{ display:block; }}

/* Day block */
.day-block {{ margin:8px 0; background:var(--card2); border-radius:6px; padding:10px 12px; }}
.day-header {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }}
.day-date {{ font-weight:700; font-size:.92rem; min-width:70px; }}
.day-sun {{ color:var(--dim); font-size:.74rem; opacity:.8; }}
.day-summary {{ color:var(--dim); font-size:.78rem; }}
.day-vis {{ font-size:.78rem; font-weight:600; }}
.day-rating {{ font-size:.88rem; font-weight:600; }}

/* Tide */
.tide-strip {{ display:flex; gap:4px; flex-wrap:wrap; margin:4px 0 6px; font-size:.74rem; }}
.tide-item {{ padding:2px 6px; border-radius:10px; white-space:nowrap; }}
.tide-h {{ font-size:.6rem; opacity:.7; margin-left:2px; }}
.tide-high {{ background:rgba(38,166,154,.15); color:var(--tide-hi); }}
.tide-low {{ background:rgba(77,208,225,.12); color:var(--tide-lo); }}

/* Detail table */
.detail-table {{ width:100%; border-collapse:collapse; font-size:.76rem; }}
.detail-table th {{ color:var(--dim); text-align:left; padding:3px 4px; font-weight:400; border-bottom:1px solid rgba(255,255,255,.08); }}
.detail-table td {{ padding:3px 4px; border-bottom:1px solid rgba(255,255,255,.04); }}
.d-time {{ color:var(--dim); font-variant-numeric:tabular-nums; min-width:36px; }}
.d-wh-cell {{ display:flex; align-items:center; gap:2px; min-width:42px; }}
.wh-mini {{ width:3px; height:14px; border-radius:2px; flex-shrink:0; }}
.wh-mini.wh-c1 {{ background:linear-gradient(180deg,var(--wave1),var(--wave2)); }}
.wh-mini.wh-c2 {{ background:linear-gradient(180deg,var(--wave2),var(--wave3)); }}
.wh-mini.wh-c3 {{ background:linear-gradient(180deg,var(--wave3),var(--wave4)); }}
.wh-mini.wh-c4 {{ background:linear-gradient(180deg,#ff4081,#d50000); }}
.wh-mini.wh-c0 {{ background:rgba(255,255,255,.15); }}
.d-wh-num {{ font-weight:800; font-size:.82rem; font-variant-numeric:tabular-nums; color:#fff; text-shadow:0 0 6px rgba(0,0,0,.6); }}
.d-wp {{ font-variant-numeric:tabular-nums; min-width:28px; }}
.d-dir {{ min-width:24px; }}
.d-ws {{ min-width:52px; }}
.d-ws-num {{ font-weight:700; }}
.d-ws-dir {{ color:var(--dim); font-size:.7rem; }}
.d-weather-cell {{ min-width:48px; }}
.d-weather {{ color:var(--dim); }}
.d-rain {{ color:var(--vis-bad); font-size:.7rem; margin-left:2px; }}

/* Responsive */
@media(max-width:600px) {{
  .rank-table {{ font-size:.7rem; }}
  .rank-table th, .rank-table td {{ padding:5px 3px; }}
  .detail-table {{ font-size:.66rem; }}
  .detail-table th, .detail-table td {{ padding:2px 3px; }}
  .d-wh-num {{ font-size:.72rem; }}
  .d-time {{ min-width:30px; }}
  .d-wh-cell {{ min-width:36px; }}
  .d-wp {{ min-width:22px; }}
  .d-dir {{ min-width:20px; }}
  .d-ws {{ min-width:40px; }}
  .d-ws-dir {{ display:none; }}
  .d-weather-cell {{ min-width:36px; }}
}}

.footer {{ text-align:center; color:var(--dim); font-size:.72rem; margin-top:32px; padding:16px 0; border-top:1px solid var(--border); }}
</style>
</head>
<body>

<div class="hero">
  <h1>🤿 潛點台灣</h1>
  <p class="sub">東北角 + 墾丁 + 綠島 + 蘭嶼 15 潛點 · {escape(today_label)} · 4 日預報</p>
  <p class="meta">CWA 鄉鎮沿海 + Open-Meteo Marine · 產生時間 {escape(generated)}</p>
</div>

<div class="ranking">
  <h2>🏆 本週潛水推薦</h2>
  <table class="rank-table">
    <thead><tr><th>#</th><th>潛點</th><th>地形</th><th>最佳日</th><th>浪高</th><th>風速</th><th>天氣</th><th>能見度</th><th>評分</th></tr></thead>
    <tbody>{ranking_rows}</tbody>
  </table>
</div>

{dive_cards}

<div class="footer">
  潛點台灣 Dive Taiwan · 資料來源：CWA 鄉鎮沿海預報 + Open-Meteo Marine API<br>
  灣內/內灣浪高已依地形修正 · 能見度為推估值（依降雨+浪高間接推估）<br>
  風速 1 m/s ≈ 1.94 節（kt）· 浪高為有效波高（Significant Wave Height）
</div>

<script>
function toggleSpot(id) {{
  var fc = document.getElementById('fc-' + id);
  var tg = document.getElementById('toggle-' + id);
  if (fc.classList.contains('open')) {{
    fc.classList.remove('open');
    tg.classList.remove('open');
  }} else {{
    fc.classList.add('open');
    tg.classList.add('open');
  }}
}}
document.querySelectorAll('.spot-head').forEach(function(el) {{
  el.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' || e.key === ' ') {{
      e.preventDefault();
      el.click();
    }}
  }});
}});
</script>

</body>
</html>"""


# ─── Main ───

if __name__ == "__main__":
    import os
    html = generate_report()
    out_dir = os.path.join(os.path.dirname(__file__), "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report generated: {out_path}")
    print(f"File size: {os.path.getsize(out_path)} bytes")
