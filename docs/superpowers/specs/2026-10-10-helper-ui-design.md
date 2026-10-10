# wavvie helper UI: design

Date: 2026-10-10. Status: approved in conversation (direction A, section 1 explicitly; the user then asked to continue without further check-ins).

## Intent

wavvie should feel like a helper, not a rocket machine. You open it, press one button, and the new songs from artists you follow land in a private Spotify playlist. It remembers which dates it already covered and offers the next window ("Your last check covered 10 Sep – 10 Oct. Check 10 Oct – today?").

What the user said:
- One button, straight to a playlist, with no review step.
- Store last-run dates and offer the next window, ending today.
- A new playlist per run, named by its dates, with a little "wavvie" in the name.
- Dark, with a fresh colour scheme. Same fonts (Loubag and Agrandir) and the wavvie wordmark.
- Every visible button must do what it says.

Constraints carried over:
- The job is unchanged: find new releases from followed artists and save them to a private playlist.
- Power options move out of the main path; they don't disappear.
- The CLI stays as it is, apart from the description tweak noted under "Playlists".
- The Spotify service, workers, paging and duplicate rules are unchanged.

Success:
- From launch to playlist takes one click, with no settings involved.
- No screen shows internals: index numbers, thread counts, cache files, env variable names or log levels.
- An automated test clicks every visible button in every state and checks its effect.

## Screens and flow

One window with a slim header and a single content column. There is no sidebar.

### Header
The wordmark sits on the left. On the right are the account avatar (Spotify image or initial, with the name in its tooltip) and a quiet **Settings** text button. Text was chosen over a gear icon because it's clearer and needs no extra asset. The header is hidden on the setup and sign-in screens.

### Setup (no credentials found)
Headline: "Connect wavvie to Spotify". Three numbered steps, a true sequence:
1. "Create an app in the Spotify developer dashboard." Quiet button: **Open dashboard** (opens https://developer.spotify.com/dashboard).
2. "Add this redirect URI to the app:" shows `http://127.0.0.1:8888/callback` as selectable text, with a quiet **Copy** button that shows "Copied" for 2 s.
3. "Paste the app's Client ID and Client secret." Two fields: "Client ID", and "Client secret" with password echo.

Primary button: **Save and continue**. It validates both fields and shows inline errors ("Enter the Client ID", "Enter the Client secret"). It writes `.env` in the working directory, reloads the environment, then shows Sign-in. Footnote: "These stay on this computer, in a .env file next to wavvie."

### Sign-in
- Headline: "New music from the artists you follow".
- Body: "wavvie checks who you follow on Spotify and saves their new songs to a private playlist."
- Primary button: **Connect Spotify**.
- While waiting: the body reads "Waiting for you to approve wavvie in your browser…", the primary button is hidden, and a quiet **Cancel** button releases the wait.
- On failure: "Couldn't connect to Spotify. Check that your app's redirect URI is http://127.0.0.1:8888/callback, then try again." Connect is shown again.

### Home
One state-driven area. Below it, "Earlier checks" lists the last five checks, but only in the waiting-to-check states.

| State | Headline | Body | Actions |
| --- | --- | --- | --- |
| Loading artists | "Getting your artists…" | none | none |
| No artists | "You don't follow any artists yet" | "Follow artists in Spotify, then refresh your artist list." | **Refresh artist list** |
| Artists failed | "Couldn't load your artists" | plain error | **Try again** |
| First run | "Let's find your new music" | "wavvie will check the {n} artists you follow and save anything released in the last {d} days to a private playlist." | **Check the last {d} days**, quiet Change dates |
| Ready | "New music since {start}" | "Your last check covered {a} – {b} and saved {k} songs." (or "…and found nothing new.") | **Check {start} – today**, quiet Change dates |
| Up to date (newest check is complete and ran today) | "You're up to date" | "Your last check ran today and saved {k} songs." | **Check again**, quiet Change dates |
| Finish last check (last check incomplete) | "Let's finish your last check" | "Your last check didn't cover everything, so wavvie will look at {start} – today again and skip songs it already saved." (The cause can be failed artists, an artist range or a partly saved playlist.) | **Check {start} – today**, quiet Change dates |
| Checking | "Checking your {n} artists…" | wave line; "{x} of {n} artists · {s} new songs so far"; when rate limited: "Spotify asked wavvie to slow down. Continuing in about {t} s." | quiet **Stop** (then "Stopping…", disabled) |
| Saving | "Saving {k} songs to Spotify…" | none | none |
| Done | "{k} new songs saved" (singular "1 new song saved") | "In your new playlist “{name}”."; optional coral note (see below); optional "A copy was saved to {file}." | **Open in Spotify**, quiet Done, quiet Show file (only if a JSON copy was saved; it opens the folder containing the file); song list |
| Partly saved | "{added} of {k} songs saved" | coral: "Spotify stopped responding while adding songs. Open the playlist to check it; your next check will pick up the rest." | **Open in Spotify**, quiet Done; song list |
| Nothing new | "Nothing new since {start}" | "No playlist was made. Check again in a few days."; optional coral notes | quiet Done |
| Not saved (playlist creation failed) | "Your songs weren't saved" | "wavvie found {k} new songs, but Spotify didn't create the playlist. {error}" | **Try saving again**, quiet Done |
| Stopped | "Check stopped" | "Nothing was saved." | quiet Done |
| Failed | "That check didn't finish" | plain error | **Try again**, quiet Done |

Coral notes on Done:
- Some artists failed: "Some artists couldn't be checked. Your next check will look at these dates again." There is no count, because scan warnings don't map one-to-one to artists. The same note is shown on "Nothing new" when it applies.
- Artist range set: "Only artists {x}–{y} were checked, so your next check will look at these dates again."

Change dates reveals an inline row: "Check from [date picker] to today". The picker allows today or earlier. The primary label follows the picked date. A quiet **Use suggested dates** button reverts. The choice applies to the next check only.

The song list shows one row per saved song: 40 px artwork (loaded lazily), title, artists (elided, full text in tooltip), release date ("9 Oct"), and a small "feature" tag when the followed artist is a guest. Clicking a row or pressing Enter opens the track in Spotify.

Earlier checks rows show "{a} – {b}", "{k} songs" or "Nothing new", and a quiet **Open in Spotify** when a playlist exists.

### Settings
This page replaces the content area. **Done** (top right) or Esc returns to Home, and Ctrl+, opens it.
- **Spotify account:** "Connected as {name}", quiet danger button **Disconnect**.
- **First check:** "When there are no earlier checks, look back" with options 7, 30, 90 and 180 days (default 30).
- **Advanced** (collapsed behind a quiet **Show advanced settings** toggle):
  - "Only check some artists", a checkbox with "From [n] to [n]" (alphabetical, both included).
  - "Parallel checks", 1–20, default 5. Helper text: "Lower this if Spotify often asks wavvie to slow down."
  - "Also save a JSON file of each check", default off. When it's on, the songs about to be saved are written as `tracklist_*.json` in the working directory right after the scan, before the playlist is created.
  - "Reduce motion".
  - **Refresh artist list**.
  - **View activity log**, which opens a dialog showing the log with **Copy log** and **Close**. Ctrl+L also opens it.
- Settings save on change. Helper text under the page: "Changes are saved automatically."

### Removed
The following go:
- The sidebar, tips card and stats cards.
- The circular visualizer.
- The New Release Scan form, the Results page (with its filters, search, selection and detail panel) and the Activity page.
- The top notice banner and the duplicate progress view.
- The playlist name and description settings, the "create playlist after scan" toggle, and the Ctrl+F shortcut.

## Dates, history and playlists

`core/history.py` is Qt-free and unit-tested.

- `CheckRecord` holds:
  - `start` and `end` (ISO dates, both inclusive; `end` is the day the check ran);
  - `ran_at` (ISO datetime);
  - `songs` (int), `playlist_name` and `playlist_url` (both optional);
  - `complete` (bool), `artist_range` (optional "x–y") and `track_ids` (list).
- `CheckHistory` is a newest-first list of records. It serialises to and from JSON and keeps 20 records.
- After each record is added, `track_ids` are kept only on records the next window overlaps (`end` ≥ next start). That keeps the stored list bounded while preserving everything the skip set needs.
- Storage is QSettings key `check_history/<spotify user id>`. MainWindow owns loading and saving. A check's `end` is the date when the check started.

Next window, where `end` is always today:
1. No records: start = today − look-back days.
2. Otherwise, take the trailing run of incomplete records (newest first, up to the newest complete record). If any exist, start = the oldest start among them.
3. Otherwise, start = the newest record's `end`. This overlaps by one day, because Spotify release dates have no time of day.

Skip set: the `track_ids` of every record whose `end` ≥ the new start. Those songs are removed from the scan result before saving.

Outcome rules:

| Outcome | Playlist | Record |
| --- | --- | --- |
| Stopped, or failed before results | none | none |
| Zero songs left after skipping | none | songs=0, no playlist; `complete` = no warnings and no artist range |
| Songs found and playlist fully saved | created | `complete` = no warnings and no artist range |
| Playlist partly saved | created | incomplete, with the first `tracks_added` IDs (batches are added in order) |
| Playlist not created | none | none; the found songs stay in memory for "Try saving again" |

Playlists:
- The name is "wavvie · New releases {a} – {b}", with dates as "10 Oct". The year is added to both dates when they differ in year, and a single-day window is "wavvie · New releases 17 Oct".
- The description is "New releases from artists you follow, {a} – {b} {year}. Made with wavvie."
- They stay private.
- If an Advanced artist range is set, the service's existing " (Artists x-y)" name suffix still applies.
- Service tweak: the description gets " - Range: x-y" only when the scan didn't cover every followed artist, mirroring the name suffix. The CLI's full-scan description loses the redundant range.

## Visual system

Palette "low tide":

| Token | Hex | Use |
| --- | --- | --- |
| DEEP | #0F2326 | window background |
| SURFACE | #163338 | inputs, song row hover, dialogs |
| RAISED | #1D4047 | hover on surfaces, avatar, tags |
| LINE | #2A5259 | hairlines, input borders |
| FOAM | #EEF5F1 | primary text |
| MIST | #9DBAB6 | secondary text |
| SUN | #F7C873 | the one primary button, progress |
| SUN_HOVER | #FFD68F | primary hover |
| ON_SUN | #0F2326 | text on SUN |
| CORAL | #FF9A8B | problems and errors |
| SEA | #8FE3B0 | small confirmations ("Copied") |

Type:
- Headlines are Loubag, 34 px, on every page.
- Body text is Agrandir 15 px. Secondary text is 13 px and meta text is 12 px.
- Buttons are Agrandir 15 px bold.
- Everything is sentence case: no all-caps labels, no negative letter spacing.

Layout:
- A single column, max 600 px wide, centred in the window with left-aligned text.
- The window defaults to 900×680, with a minimum of 720×560. Content scrolls vertically when it's long; it never scrolls horizontally.

Components:
- **Primary button:** SUN pill, 44 px tall.
- **Quiet button:** text in MIST, underlined on hover.
- **Danger quiet button:** CORAL text.
- **Rows:** separated by hairlines, not cards.
- **Focus:** a visible 2 px FOAM focus ring on every control.

Motion: one `WaveLine` widget appears while checking. A travelling wave is drawn over the completed share of the line, with a flat LINE colour after it. It is static under reduced motion, and its timer runs only while it's visible and checking.

Accessibility: every control has an accessible name, label buddies are set, and keyboard paths cover every action.

## Code structure

New:
- `core/history.py`.
- `ui/pages/setup_page.py`.
- `ui/pages/sign_in_page.py`.
- `ui/pages/home_page.py`, with the state views, song list and earlier checks.
- `ui/widgets/wave_line.py`.
- `ui/widgets/activity_log.py`, a dialog built from the old Activity page's log handler.

Rewritten:
- `ui/theme.py`.
- `ui/main_window.py`, the orchestrator. It keeps one operation at a time, cooperative cancel, close waiting for workers, and cancel sign-in. A check runs scan → skip saved songs → create playlist → record history.
- `ui/pages/settings_page.py`.

Kept: `ui/widgets/elided_label.py`, `ui/resources.py`, `ui/font_loader.py`, `core/workers.py` and `core/models.py`.

Small changes:
- `core/spotify_service.py` gets the description tweak.
- `main.py` gains `save_environment()` next to `load_environment()`.

Deleted:
- `ui/widgets/sidebar.py`, `ui/widgets/circular_visualizer.py`.
- `ui/pages/dashboard_page.py`, `scan_page.py`, `results_page.py`, `activity_page.py` and `auth_page.py`.

## Testing

- `tests/test_history.py` covers:
  - next-window rules: first run, after a complete check, a chain of incomplete checks, and same day;
  - the skip set, trimming and a JSON round trip;
  - playlist names: same month, across months, across years and a single day.
- `tests/test_desktop_ux.py` is rewritten for the new UI. It uses real widgets, isolated QSettings and a fake service and workers, and covers:
  - setup writing `.env`;
  - sign-in, its cancel button, and closing during sign-in;
  - every home state;
  - one-click check → dated playlist → history → next suggestion;
  - nothing new, warnings, a partial playlist, a failed playlist with retry, and stop;
  - change dates;
  - settings persistence;
  - closing during a check;
  - layouts at 720×560, 900×680 and 1600×1000, plus 150% scaling and long names.
- An "every button" test walks every state, clicks each visible button, and asserts a named effect from a table. A button without an entry fails the test.
- The old UI tests in `tests/test_spotify_release_tool.py` are removed. Its service, font and letter-spacing tests stay.
- Visual check: the screenshot tour is re-run for every state, reviewed, and fixed before finishing.
