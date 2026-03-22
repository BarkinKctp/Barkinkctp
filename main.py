import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
import gifos

START_YEAR = 2024
FONT_FILE_BITMAP = os.path.join(
    os.path.dirname(gifos.__file__), "fonts", "gohufont-uni-14.pil"
)


def fetch_streaks(username: str, token: str) -> tuple[int, int]:
    # Return (current_streak, longest_streak) from GitHub 
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": username}},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()

    data = resp.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted(
        [day for week in data["weeks"] for day in week["contributionDays"]],
        key=lambda d: d["date"],
    )
    today = date.today()

    # Current streak 
    current = 0
    for day in reversed(days):
        d = date.fromisoformat(day["date"])
        if d > today:
            continue
        if day["contributionCount"] > 0:
            current += 1
        elif d != today:
            break

    longest, running = 0, 0
    for day in days:
        d = date.fromisoformat(day["date"])
        if d > today:
            break
        if day["contributionCount"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    return current, longest


def main():
    t = gifos.Terminal(620, 420, 12, 12, FONT_FILE_BITMAP, 15)

    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    years_exp = now.year - START_YEAR
    year_now = now.strftime("%Y")
    time_now = now.strftime("%a %b %d %I:%M:%S %p %Z %Y")
    token = os.environ.get("GITHUB_TOKEN", "") ## Using the GitHub token created by Github Actions (Not PAT)

    # ── Fetch GitHub stats ─────────────────────────────────────────────────────
    github_stats = gifos.utils.fetch_github_stats("BarkinKctp")
    top_languages = [lang[0] for lang in github_stats.languages_sorted]
    try:
        current_streak, longest_streak = fetch_streaks("BarkinKctp", token)
    except Exception:
        current_streak, longest_streak = "?", "?"

    user_details = f"""
\x1b[30;101mbarkinkctp@GitHub\x1b[0m
-----------------
\x1b[96mRole:        \x1b[93mEngineer - DevOps / Cloud\x1b[0m
\x1b[96mFocus:       \x1b[93mPlatform automation · CI/CD · IaC\x1b[0m
\x1b[96mStack:       \x1b[93mCloud · K8s · Docker · Terraform\x1b[0m
\x1b[96mExp:         \x1b[93m{years_exp}+ years\x1b[0m

\x1b[30;101mGitHub Stats:\x1b[0m
-----------------
\x1b[96mRating:      \x1b[93m{github_stats.user_rank.level}\x1b[0m
\x1b[96mCommits ({int(year_now) - 1}): \x1b[93m{github_stats.total_commits_last_year}\x1b[0m
\x1b[96mContribs:    \x1b[93m{github_stats.total_repo_contributions}\x1b[0m
\x1b[96mStreak:  \x1b[93m{current_streak}d\x1b[96m  |  Longest:  \x1b[93m{longest_streak}d\x1b[0m
\x1b[96mLanguages:   \x1b[93m{', '.join(top_languages[:5])}\x1b[0m

\x1b[30;101mContact:\x1b[0m
-----------------
\x1b[96mLinkedIn:    \x1b[93min/Barkin-Kocatepe\x1b[0m
"""

    # Sequence

    # 1. echo "Hi, I'm Barkin Kocatepe"
    t.gen_prompt(1, count=5)
    t.toggle_show_cursor(True)
    t.gen_typing_text('echo "Hi, I\'m Barkin Kocatepe"', 1, contin=True)
    t.toggle_show_cursor(False)
    t.gen_text("\x1b[93mHi, I'm Barkin Kocatepe\x1b[0m", 3, count=10)

    # 2. fetch.sh -u barkinkctp  
    t.gen_prompt(5, count=5)
    prompt_col = t.curr_col
    t.toggle_show_cursor(True)
    t.gen_typing_text("\x1b[91mfetch.s", 5, contin=True)
    t.delete_row(5, prompt_col)
    t.gen_text("\x1b[92mfetch.sh\x1b[0m", 5, contin=True)
    t.gen_typing_text(" -u barkinkctp", 5, contin=True)
    t.toggle_show_cursor(False)

    # 3. Neofetch output
    t.gen_text(user_details, 7, count=5, contin=True)

    # 4. Closing prompt + clear
    t.gen_prompt(t.curr_row + 1)
    prompt_col = t.curr_col
    t.clone_frame(15)
    t.toggle_show_cursor(True)
    t.gen_typing_text("\x1b[91mclea", t.curr_row, contin=True)
    t.delete_row(t.curr_row, prompt_col)
    t.gen_text("\x1b[92mclear\x1b[0m", t.curr_row, count=5, contin=True)
    t.toggle_show_cursor(False)

    # 5. Blank pause before GIF loops
    t.gen_text("", 1, count=30)

    t.gen_gif()
    print(f"INFO: output.gif generated — {time_now} | streak: {current_streak} days | longest: {longest_streak} days")


if __name__ == "__main__":
    main()