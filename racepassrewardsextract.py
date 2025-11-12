# racepassrewardsextract.py
import json
import os
import re
import sys
import subprocess
import importlib
from datetime import datetime

# ------------------------------------------------------------
# Auto-install missing packages
# ------------------------------------------------------------
required_packages = {
    "UnityPy": "UnityPy",
    "colorama": "colorama",
}

def install_if_missing(packages: dict[str, str]) -> None:
    for pip_name, import_name in packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"Installing missing package: {pip_name}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

install_if_missing(required_packages)

# Safe imports
import UnityPy
from colorama import init, Fore, Style
init(autoreset=True)

# Console colours
RED    = Fore.RED
BLUE   = Fore.BLUE
WHITE  = Fore.WHITE
YELLOW = Fore.YELLOW
RESET  = Style.RESET_ALL

# ------------------------------------------------------------
# Translation & Theme helpers
# ------------------------------------------------------------
def find_translation_file():
    """Search current folder → MonoBehaviour → none."""
    candidates = []

    # 1. Current directory
    cur = [f for f in os.listdir(".") if os.path.isfile(f) and re.search(r"translationdataasset", f, re.IGNORECASE)]
    candidates.extend([os.path.abspath(f) for f in cur])

    # 2. MonoBehaviour sub-folder
    mb = "MonoBehaviour"
    if os.path.isdir(mb):
        mb_files = [f for f in os.listdir(mb) if os.path.isfile(os.path.join(mb, f))
                    and re.search(r"translationdataasset", f, re.IGNORECASE)]
        candidates.extend([os.path.join(mb, f) for f in mb_files])

    if not candidates:
        print(f"{YELLOW}TranslationDataAsset.json not found – using raw names.{RESET}")
        return None

    chosen = sorted(candidates)[0]
    print(f"{YELLOW}Using translation file:{RESET} {chosen}")
    return chosen


def build_translation_lookup(path):
    """Return {car_id: name, theme_key: theme_name}."""
    if not path:
        return {}, {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except Exception as e:
            print(f"{RED}Failed to decode translation file: {e}{RESET}")
            return {}, {}
    except Exception as e:
        print(f"{RED}Failed to load translation file: {e}{RESET}")
        return {}, {}

    car_map = {}
    theme_map = {}

    from_keys = data.get("TranslationsFrom", [])
    to_values = data.get("TranslationsTo", [])

    for k, v in zip(from_keys, to_values):
        if k.startswith("TEXT_CAR_") and k.endswith("_LONG"):
            code = k[len("TEXT_CAR_"):-len("_LONG")]
            car_map[code] = v
        elif k.startswith("TEXT_SEASON_PASS_NEWSPANEL_THEME_NAME_SEASON"):
            # e.g. TEXT_SEASON_PASS_NEWSPANEL_THEME_NAME_SEASON45 → Season 45
            match = re.search(r"SEASON(\d+)$", k)
            if match:
                season_num = match.group(1)
                theme_map[season_num] = v
        else:
            # Keep other translations if needed later
            pass

    file_date = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y/%m/%d")
    print(f"{YELLOW}Translation lookup built – {len(car_map)} cars, {len(theme_map)} themes ({os.path.basename(path)} – {file_date}){RESET}")
    return car_map, theme_map


# ------------------------------------------------------------
# Load season-pass data
# ------------------------------------------------------------
FILE_PATH = "SeasonPassMilestoneRewards.meta"
try:
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"{RED}Error: '{FILE_PATH}' not found.{RESET}")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"{RED}JSON parse error: {e}{RESET}")
    sys.exit(1)

# Load translations & themes
translation_path = find_translation_file()
car_translation_map, theme_map = build_translation_lookup(translation_path)

rewards_root = data.get("SeasonPassMilestoneRewards", {})
console_lines = []
file_lines = []


def format_car(car_id: str) -> str:
    """Return 'Translated Name (DBID)' or just 'DBID'."""
    if car_translation_map and car_id in car_translation_map:
        return f"{car_translation_map[car_id]} ({car_id})"
    return car_id


def get_season_title(base: str, season_num: str) -> str:
    """Add theme if available: 'Season 45 - SNOWBALL SPRINT'"""
    theme = theme_map.get(season_num)
    if theme:
        return f"{base} - {theme}"
    return base


def add_season(title_base: str, season_num: str, paid: list, free: list):
    title = get_season_title(title_base, season_num)

    # --- Console (colored) ---
    console_lines.append(f"{RED}Race Pass - {title}{RESET}")
    console_lines.append("")
    console_lines.append(f"{BLUE}Paid:{RESET}")
    for c in paid:
        console_lines.append(f"{WHITE}{format_car(c)}{RESET}")
    console_lines.append("")
    console_lines.append(f"{BLUE}Free:{RESET}")
    for c in free:
        console_lines.append(f"{WHITE}{format_car(c)}{RESET}")
    console_lines.append("-------------------------------------------")
    console_lines.append("")

    # --- File (plain) ---
    file_lines.append(f"Race Pass - {title}")
    file_lines.append("")
    file_lines.append("Paid:")
    for c in paid:
        file_lines.append(format_car(c))
    file_lines.append("")
    file_lines.append("Free:")
    for c in free:
        file_lines.append(format_car(c))
    file_lines.append("-------------------------------------------")
    file_lines.append("")


# ------------------------------------------------------------
# Rookie Seasons
# ------------------------------------------------------------
for key, info in rewards_root.get("RookieRewardContainers", {}).items():
    # Extract number: RookieSeason1 → "1"
    match = re.search(r"RookieSeason(\d+)", key)
    season_num = match.group(1) if match else ""
    season_title = key.replace("RookieSeason", "Rookie Season ")

    paid = [
        r["reward"]["name"] for r in info.get("NewPaidTrackRewards", [])
        if r.get("reward", {}).get("rewardType") == 11 and "name" in r.get("reward", {})
    ]
    free = []
    for b in info.get("FreeTrack", {}).get("brackets", []):
        if b.get("isFinalReward"):
            free = [
                r["reward"]["name"] for r in b.get("rewards", [])
                if r.get("reward", {}).get("rewardType") == 11 and "name" in r.get("reward", {})
            ]
            break
    add_season(season_title, season_num, paid, free)


# ------------------------------------------------------------
# Regular Seasons
# ------------------------------------------------------------
for key, info in rewards_root.get("RewardContainers", {}).items():
    # Extract number: Season45 → "45"
    match = re.search(r"Season(\d+)", key)
    season_num = match.group(1) if match else ""
    season_title = key.replace("Season", "Season ")

    paid = [
        r["reward"]["name"] for r in info.get("NewPaidTrackRewards", [])
        if r.get("reward", {}).get("rewardType") == 11 and "name" in r.get("reward", {})
    ]
    free = []
    for b in info.get("FreeTrack", {}).get("brackets", []):
        if b.get("isFinalReward"):
            free = [
                r["reward"]["name"] for r in b.get("rewards", [])
                if r.get("reward", {}).get("rewardType") == 11 and "name" in r.get("reward", {})
            ]
            break
    add_season(season_title, season_num, paid, free)


# ------------------------------------------------------------
# Output
# ------------------------------------------------------------
print("\n".join(console_lines))

output_file = "race_pass_rewards.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(file_lines))

print(f"\n{YELLOW}Plain output saved to '{output_file}'{RESET}")