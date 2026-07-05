from playwright.sync_api import sync_playwright
import json
import time
import re
import os
import sys

SCORECARD_LIST_URL = "https://connect.garmin.com/app/scorecards/900d8263-6f06-4eb3-888a-e366dee03167"
OUTPUT_DIR = r"C:\Users\gragg\Projects\GolfAnalytics\Data"
USER_DATA_DIR = r"C:\Users\gragg\garmin-automation\User Data"
PROFILE_DIR = "Profile 5"
DELAY_SECONDS = 2
MAX_SCORECARDS = 500  # safety cap

os.makedirs(OUTPUT_DIR, exist_ok=True)


def refresh_login():
    print("\n--- Session expired or invalid. Refreshing login. ---")
    with sync_playwright() as p:
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


def get_latest_scorecard_id(context):
    """
    Navigates to the scorecard list page and tries to find the newest scorecard ID.
    Strategy 1: intercept any JSON API response that looks like a scorecard list.
    Strategy 2 (fallback): scrape /app/scorecard/<id> links out of the rendered HTML.
    """
    page = context.new_page()
    intercepted_ids = []

    def handle_response(response):
        if response.request.resource_type in ("xhr", "fetch") and response.status == 200:
            ct = response.headers.get("content-type", "")
            if "json" in ct.lower():
                try:
                    body = response.json()
                except Exception:
                    return
                # Dump the URL so we can see what came back if IDs aren't found
                found = re.findall(r'"scorecardId"\s*:\s*(\d+)', json.dumps(body))
                if found:
                    print(f"  [intercepted] {response.url} -> found IDs: {found[:5]}...")
                    intercepted_ids.extend(int(i) for i in found)

    page.on("response", handle_response)

    print(f"Navigating to scorecard list: {SCORECARD_LIST_URL}")
    page.goto(SCORECARD_LIST_URL, timeout=30000)
    page.wait_for_timeout(4000)  # let list + API calls settle

    if intercepted_ids:
        newest = max(intercepted_ids)
        print(f"Newest scorecard ID from intercepted API data: {newest}")
        page.close()
        return str(newest)

    # Fallback: scrape rendered HTML for scorecard links
    html = page.content()
    ids = re.findall(r'/app/scorecard/(\d+)', html)
    page.close()

    if ids:
        unique_ids = sorted(set(int(i) for i in ids), reverse=True)
        print(f"Newest scorecard ID from HTML scrape: {unique_ids[0]} (found {len(unique_ids)} total links)")
        return str(unique_ids[0])

    print("Could not find any scorecard ID on the list page. Manual check needed.")
    return None


def fetch_scorecard(context, scorecard_id):
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

        current_id = get_latest_scorecard_id(context)
        if not current_id:
            print("Stopping — no starting scorecard ID found.")
            context.close()
            sys.exit(1)

        while current_id and collected < MAX_SCORECARDS:
            status, data = fetch_scorecard(context, current_id)

            if status == 200 and data is not None:
                refreshed_this_round = False

                out_path = os.path.join(OUTPUT_DIR, f"scorecard_{current_id}.json")
                with open(out_path, "w") as f:
                    json.dump(data, f, indent=2)
                collected += 1
                print(f"[{collected}] Saved scorecard {current_id}")

                try:
                    details = data.get("scorecardDetails", [{}])[0]
                    next_prev = details.get("nextPreviousScorecardIdsApiModel", {})
                    prev_id = next_prev.get("previousScorecardId")
                except Exception:
                    prev_id = None

                if not prev_id:
                    print("No previous scorecard ID found. Reached the oldest round.")
                    break

                current_id = str(prev_id)
                time.sleep(DELAY_SECONDS)

            else:
                print(f"Failed on scorecard {current_id}. Status: {status}")

                if not refreshed_this_round:
                    context.close()
                    refresh_login()
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

    print(f"\nDone. Collected {collected} scorecards.")


if __name__ == "__main__":
    main()