import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

# ── Config ────────────────────────────────────────────────────────────────────
USERNAME = "BarkinKctp"
START_YEAR = 2024
FPS = 15
W, H       = 720, 520
XPAD, YPAD = 16, 38
LINE_H     = 18
FONT_SIZE = 13

BG        = "#0a0a0a"   
BORDER    = "#454545"  
PROMPT_C  = "#58a6ff"   # blue
DIM_C     = "#8b949e"   # gray
GREEN_C   = "#3fb950"   # green
WHITE_C   = "#e6edf3"   # white
LABEL_C   = "#58a6ff"   # blue
VALUE_C   = "#e6edf3"   # white
SEP_C     = "#30363d"   # dark gray
RED_C     = "#ff5f57"
ORANGE_C  = "#febc2e"
DOT_G     = "#28c840"


# GitHub stats
def fetch_json(method: str, url: str, **kwargs) -> dict | list:
    response = requests.request(method, url, timeout=15, **kwargs)
    response.raise_for_status()
    return response.json()


def fetch_stats(token: str, current_year: int) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    commit_year = current_year - 1
    commits_resp = fetch_json(
        "GET",
        f"https://api.github.com/search/commits?q=author:{USERNAME}+author-date:{commit_year}-01-01..{commit_year}-12-31&per_page=1",
        headers={**headers, "Accept": "application/vnd.github.cloak-preview+json"},
    )
    last_year_commits = commits_resp.get("total_count", 0)

    gql = fetch_json(
        "POST",
        "https://api.github.com/graphql",
        json={
            "query": """query($login:String!){user(login:$login){
  contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{contributionCount date}}}}
  repositories(first:100 ownerAffiliations:OWNER isFork:false){nodes{languages(first:5 orderBy:{field:SIZE direction:DESC}){edges{size node{name}}}}}
}}""",
            "variables": {"login": USERNAME},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    if "errors" in gql:
        raise ValueError(gql["errors"])

    _exclude = {"CSS", "Jupyter Notebook", "TypeScript", "HTML", "Makefile","PowerShell"}
    lang_bytes: dict[str, int] = {}
    for repo in gql["data"]["user"]["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in _exclude:
                lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]
    top_langs = ", ".join(sorted(lang_bytes, key=lambda l: lang_bytes[l], reverse=True)[:3]) or "N/A"

    cal = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted([d for w in cal["weeks"] for d in w["contributionDays"]], key=lambda d: d["date"])
    today = date.today()

    current = 0
    for day in reversed(days):
        d = date.fromisoformat(day["date"])
        if d > today:
            continue
        if day["contributionCount"] > 0:
            current += 1
        elif d != today:
            break

    longest = running = 0
    for day in days:
        d = date.fromisoformat(day["date"])
        if d > today:
            break
        if day["contributionCount"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    return {
        "top_langs": top_langs,
        "last_year_commits": last_year_commits,
        "commit_year": commit_year,
        "total_contribs": cal["totalContributions"],
        "current_streak": current,
        "longest_streak": longest,
    }


# Helpers
def load_font(size=FONT_SIZE):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", size)
    except Exception:
        return ImageFont.load_default()

def load_font_bold(size=FONT_SIZE):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", size)
    except Exception:
        return load_font(size)

def new_frame(font, font_bold):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    #Border
    draw.rounded_rectangle([0, 0, W-1, 28], radius=8, fill="#1c1c1c") 
    # Title bar dots
    draw.rectangle([0, 20, W-1, 28], fill="#1c1c1c")

    draw.rounded_rectangle([0, 0, W-1, H-1], radius=8, outline=BORDER, width=2)

    draw.ellipse([13, 11, 24, 22], fill=RED_C)
    draw.ellipse([30, 11, 41, 22], fill=ORANGE_C)
    draw.ellipse([47, 11, 58, 22], fill=DOT_G)
    # Title bar separator
    draw.line([(2, 28), (W-2, 28)], fill="#333333", width=2)
    return img, draw

def row_y(row):
    """Convert 1-based row number to y pixel position."""
    return YPAD + (row - 1) * LINE_H

def draw_prompt(draw, row, font, font_bold):
    y = row_y(row)
    uw = int(font_bold.getlength("barkin@dev"))
    draw.text((XPAD, y), "barkin@dev", font=font_bold, fill=PROMPT_C)
    draw.text((XPAD + uw, y), ":~$ ", font=font, fill=DIM_C)
    return XPAD + uw + int(font.getlength(":~$ "))

def draw_cursor(draw, row, cmd_x, col_offset=0):
    y = row_y(row)
    draw.rectangle([cmd_x + col_offset, y+1, cmd_x + col_offset + 7, y+LINE_H-2], fill=PROMPT_C)


# Frame builder
def build_frames(stats: dict, years_exp: int):
    font = load_font()
    font_bold = load_font_bold()
    frames = []
    _uw = int(font_bold.getlength("barkin@dev"))
    cmd_x = XPAD + _uw + int(font.getlength(":~$ "))

    def snapshot(hold_frames=1):
        """Return `hold_frames` copies of the current image."""
        return [img.copy() for _ in range(hold_frames)]

    HOLD = 8   # frames to hold a stable line (~0.5s at 15fps)
    TYPE = 2   # frames per typed character

    # Precompute neofetch lines as (row_offset, segments) tuples
    # Each segment: (text, color, bold)
    neofetch = [
        # separator
        [(f"{'─'*42}", SEP_C, False)],
        # header
        [("barkinkctp", LABEL_C, True), ("@", DIM_C, False), ("github", LABEL_C, True)],
        # sep2
        [("─"*14, SEP_C, False)],
        # info
        [("Role:   ", LABEL_C, True), ("DevOps / Cloud", VALUE_C, False)],
        [("Focus:  ", LABEL_C, True), ("Platform automation · CI/CD · IaC", VALUE_C, False)],
        [("Stack:  ", LABEL_C, True), ("Cloud · K8s · Docker · Terraform", VALUE_C, False)],
        [("Exp:    ", LABEL_C, True), (f"{years_exp}+ years", VALUE_C, False)],
        [("", VALUE_C, False)],
        # stats sep
        [("─"*14, SEP_C, False)],
        [("GitHub Stats:", LABEL_C, True)],
        [("─"*14, SEP_C, False)],
        [("Contributions:  ", LABEL_C, True), (str(stats["total_contribs"]), VALUE_C, False)],
        [("Commits:        ", LABEL_C, True), (str(stats["last_year_commits"]), VALUE_C, False), (f" ({stats['commit_year']})", DIM_C, False)],
        [("Streak:         ", LABEL_C, True), (f"{stats['current_streak']}d", VALUE_C, False),
         ("  |  Longest: ",  DIM_C,   False), (f"{stats['longest_streak']}d", VALUE_C, False)],
        [("Languages:      ", LABEL_C, True), (stats["top_langs"], VALUE_C, False)],
        # contact sep
        [("─"*14, SEP_C, False)],
        [("", VALUE_C, False)],
        [("Contact Me:", LABEL_C, True)],
        [("─"*14, SEP_C, False)],
        [("LinkedIn:  ", LABEL_C, True), ("Barkin-Kocatepe", VALUE_C, False)],
        [("Email:     ", LABEL_C, True), ("barkinkocatepe12@gmail.com", VALUE_C, False)],
        [("─"*42, SEP_C, False)],
    ]

    # ── Phase 1: echo
    img, draw = new_frame(font, font_bold)
    draw_prompt(draw, 1, font, font_bold)
    frames += snapshot(HOLD)

    echo_cmd = 'echo "Hi, I\'m Barkin Kocatepe"'
    typed = ""
    for ch in echo_cmd:
        typed += ch
        img, draw = new_frame(font, font_bold)
        draw_prompt(draw, 1, font, font_bold)
        draw.text((cmd_x, row_y(1)), typed, font=font, fill=GREEN_C)
        draw_cursor(draw, 1, cmd_x, col_offset=int(font.getlength(typed)))
        frames += snapshot(TYPE)

    # Hold echo command
    img, draw = new_frame(font, font_bold)
    draw_prompt(draw, 1, font, font_bold)
    draw.text((cmd_x, row_y(1)), echo_cmd, font=font, fill=GREEN_C)
    frames += snapshot(HOLD)

    # Show echo output
    img, draw = new_frame(font, font_bold)
    draw_prompt(draw, 1, font, font_bold)
    draw.text((cmd_x, row_y(1)), echo_cmd, font=font, fill=GREEN_C)
    draw.text((XPAD, row_y(3)), "Hi, I'm Barkin Kocatepe", font=font_bold, fill=WHITE_C)
    frames += snapshot(HOLD * 4)

    # ── Phase 2: clear
    img, draw = new_frame(font, font_bold)
    draw_prompt(draw, 1, font, font_bold)
    draw.text((cmd_x, row_y(1)), echo_cmd, font=font, fill=GREEN_C)
    draw.text((XPAD, row_y(3)), "Hi, I'm Barkin Kocatepe", font=font_bold, fill=WHITE_C)
    draw_prompt(draw, 5, font, font_bold)
    frames += snapshot(HOLD)

    clear_cmd = "clear"
    typed = ""
    for ch in clear_cmd:
        typed += ch
        img, draw = new_frame(font, font_bold)
        draw_prompt(draw, 1, font, font_bold)
        draw.text((cmd_x, row_y(1)), echo_cmd, font=font, fill=GREEN_C)
        draw.text((XPAD, row_y(3)), "Hi, I'm Barkin Kocatepe", font=font_bold, fill=WHITE_C)
        draw_prompt(draw, 5, font, font_bold)
        draw.text((cmd_x, row_y(5)), typed, font=font, fill=GREEN_C)
        frames += snapshot(TYPE)

    frames += snapshot(HOLD)
    # Screen wipes — blank frame
    img, draw = new_frame(font, font_bold)
    frames += snapshot(HOLD)

    # ── Phase 3: fetch
    fetch_cmd = "./users/barkinkctp.sh"

    img, draw = new_frame(font, font_bold)
    draw_prompt(draw, 1, font, font_bold)
    frames += snapshot(HOLD)

    typed = ""
    for ch in fetch_cmd:
        typed += ch
        img, draw = new_frame(font, font_bold)
        draw_prompt(draw, 1, font, font_bold)
        # red while typing, green once complete
        color = GREEN_C if typed == fetch_cmd else "#ff6b6b"
        draw.text((cmd_x, row_y(1)), typed, font=font, fill=color)
        draw_cursor(draw, 1, cmd_x, col_offset=int(font.getlength(typed)))
        frames += snapshot(TYPE)

    frames += snapshot(HOLD)

    # Phase 4: neofetch output lines appear one by one
    visible_lines = []
    for line_segs in neofetch:
        visible_lines.append(line_segs)
        img, draw = new_frame(font, font_bold)
        draw_prompt(draw, 1, font, font_bold)
        draw.text((cmd_x, row_y(1)), fetch_cmd, font=font, fill=GREEN_C)
        row = 3
        for segs in visible_lines:
            x = XPAD
            y = row_y(row)
            for text, color, bold in segs:
                f = font_bold if bold else font
                draw.text((x, y), text, font=f, fill=color)
                x += int(f.getlength(text))
            row += 1
        frames += snapshot(HOLD)

    # Phase 5: closing prompt + cursor blink
    closing_row = 3 + len(neofetch) + 1

    def draw_neofetch_and_prompt(draw, blink_cursor=False, clear_typed=""):
        draw_prompt(draw, 1, font, font_bold)
        draw.text((cmd_x, row_y(1)), fetch_cmd, font=font, fill=GREEN_C)
        row = 3
        for segs in neofetch:
            x = XPAD
            for text, color, bold in segs:
                f = font_bold if bold else font
                draw.text((x, row_y(row)), text, font=f, fill=color)
                x += int(f.getlength(text))
            row += 1
        draw_prompt(draw, closing_row, font, font_bold)
        if blink_cursor:
            draw_cursor(draw, closing_row, cmd_x)
        if clear_typed:
            draw.text((cmd_x, row_y(closing_row)), clear_typed, font=font, fill=GREEN_C)

    for blink in range(12):
        img, draw = new_frame(font, font_bold)
        draw_neofetch_and_prompt(draw, blink_cursor=(blink % 2 == 0))
        frames += snapshot(HOLD)

    # Extra pause — full card visible, no blink, before clearing
    frames += snapshot(HOLD * 6)

    # Phase 6: clear at end
    typed = ""
    for ch in clear_cmd:
        typed += ch
        img, draw = new_frame(font, font_bold)
        draw_neofetch_and_prompt(draw, clear_typed=typed)
        frames += snapshot(TYPE)

    frames += snapshot(HOLD)

    # Blank pause before loop
    img, draw = new_frame(font, font_bold)
    frames += snapshot(HOLD * 3)

    return frames

def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    years_exp = now.year - START_YEAR
    time_now = now.strftime("%a %b %d %I:%M:%S %p %Z %Y")

    try:
        stats = fetch_stats(token, now.year)
    except Exception as e:
        print(f"WARN: stats fetch failed — {e}")
        stats = {
            "top_langs": "N/A", "last_year_commits": "?", "commit_year": now.year - 1,
            "total_contribs": "?", "current_streak": "?", "longest_streak": "?",
        }

    print(f"INFO: building frames — {stats}")
    frames = build_frames(stats, years_exp)

    frame_duration = int(1000 / FPS)  # ms per frame
    frames[0].save(
        "output.gif",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=frame_duration,
        optimize=False,
    )
    print(f"INFO: output.gif saved — {len(frames)} frames — {time_now}")


if __name__ == "__main__":
    main()