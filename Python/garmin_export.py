import sys

print(sys.executable)
print(sys.version)

from playwright.sync_api import sync_playwright
import json
import time
import os
import sys

OUTPUT_DIR = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\Data"
USER_DATA_DIR = r"C:\Users\gragg\garmin-automation\User Data"
PROFILE_DIR = "Profile 5"
DELAY_SECONDS = 2
MAX_SCORECARDS_PER_RUN = 500  # safety cap

CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.json")
OLDEST_KNOWN_SCORECARD_ID = "357643232"  # confirmed true oldest round

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_checkpoint():
    """Returns the last successfully saved scorecard ID, or the oldest known ID if no checkpoint exists yet."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_scorecard_id", OLDEST_KNOWN_SCORECARD_ID)
    return OLDEST_KNOWN_SCORECARD_ID


def save_checkpoint(scorecard_id):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"last_scorecard_id": scorecard_id}, f, indent=2)


def refresh_login(p):
    print("\n--- Session expired or invalid. Refreshing login. ---")
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        channel="chrome",
        args=[
            "--disable-blink-features=AutomationControlled",
            f"--profile-directory={PROFILE_DIR}",
        ],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://connect.garmin.com/signin")
    input("Log in manually in the opened window, then press Enter here...")
    context.close()
    print("--- Login refreshed. ---\n")


def fetch_scorecard(context, scorecard_id):
    """Navigates to a scorecard page and intercepts the detail API response."""
    page = context.new_page()
    result = {"status": -1, "data": None}

    def handle_response(response):
        if "scorecard/detail" in response.url and response.request.resource_type in ("xhr", "fetch"):
            if response.status == 200:
                try:
                    result["data"] = response.json()
                    result["status"] = 200
                except Exception:
                    pass
            else:
                result["status"] = response.status

    page.on("response", handle_response)

    try:
        page.goto(f"https://connect.garmin.com/app/scorecard/{scorecard_id}", timeout=30000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"Navigation error: {e}")
    finally:
        page.close()

    return result["status"], result["data"]


def main():
    collected = 0
    refreshed_this_round = False

    current_id = load_checkpoint()
    print(f"Starting from scorecard ID: {current_id}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--profile-directory={PROFILE_DIR}",
            ],
        )

        while current_id and collected < MAX_SCORECARDS_PER_RUN:
            status, data = fetch_scorecard(context, current_id)

            if status == 200 and data is not None:
                refreshed_this_round = False

                out_path = os.path.join(OUTPUT_DIR, f"scorecard_{current_id}.json")
                with open(out_path, "w") as f:
                    json.dump(data, f, indent=2)
                collected += 1
                print(f"[{collected}] Saved scorecard {current_id}")

                # Save checkpoint immediately after each success, so a
                # mid-run crash doesn't lose progress or re-fetch old rounds.
                save_checkpoint(current_id)

                try:
                    details = data.get("scorecardDetails", [{}])[0]
                    next_prev = details.get("nextPreviousScorecardIdsApiModel", {})
                    next_id = next_prev.get("nextScorecardId")
                except Exception:
                    next_id = None

                if not next_id:
                    print("No newer scorecard found. Caught up to most recent round.")
                    break

                current_id = str(next_id)
                time.sleep(DELAY_SECONDS)

            else:
                print(f"Failed on scorecard {current_id}. Status: {status}")

                if not refreshed_this_round:
                    context.close()
                    refresh_login(p)          # <-- pass the existing Playwright instance
                    refreshed_this_round = True
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=USER_DATA_DIR,
                        headless=True,
                        channel="chrome",
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            f"--profile-directory={PROFILE_DIR}",
                        ],
                    )
                    continue
                else:
                    print("Still failing after login refresh. Stopping.")
                    context.close()
                    sys.exit(1)

        context.close()

    print(f"\nDone. Collected {collected} new scorecard(s) this run.")


if __name__ == "__main__":
    main()