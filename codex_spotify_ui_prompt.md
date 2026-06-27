# Codex Prompt — Spotify New Releases Dashboard UI

> Feed this prompt directly to Codex (or any capable coding model).  
> The result should be a self-contained React + FastAPI app that wraps the existing `main.py`.

---

## 1. Context & Goal

You are building a **modern, geometric music dashboard** on top of an existing Python Spotify CLI tool (`main.py`). That script:
- Authenticates with Spotify OAuth
- Fetches all artists a user follows (with local JSON caching)
- Discovers new releases (albums, singles, EPs, features/collabs) since a cutoff date
- Deduplicates tracks using a `track_signature` (`track_name|artist1|artist2…`)
- Creates private Spotify playlists
- Exports a JSON tracklist file

The UI replaces the terminal entirely. The user controls everything through the dashboard; the Python script becomes the backend.

**Architecture:**
- **Backend:** Wrap `main.py`'s functions in a `FastAPI` server (`api.py`). Expose REST + Server-Sent Events (SSE) endpoints.
- **Frontend:** `React 18` app (Vite), styled with `Tailwind CSS` + CSS custom properties, animated with `Framer Motion`, charts via `Recharts`.

---

## 2. Design System

### 2a. Color Tokens
Define these as CSS custom properties on `:root` and map to Tailwind via `tailwind.config.js`.

```css
:root {
  --void:     #07070F;   /* page background          */
  --obsidian: #0F0F1A;   /* card surface             */
  --slate:    #16162A;   /* elevated surface / nav   */
  --mist:     #1E1E38;   /* border / divider         */
  --iris:     #7C3AED;   /* primary accent (purple)  */
  --iris-dim: #4C1D95;   /* iris at lower opacity    */
  --neon:     #A78BFA;   /* glow / highlight text    */
  --mint:     #10B981;   /* success / main-role tag  */
  --rose:     #F472B6;   /* featured / collab tag    */
  --amber:    #FBBF24;   /* warning / EP tag         */
  --sky:      #38BDF8;   /* info / single tag        */
  --snow:     #F1F5F9;   /* primary text             */
  --comet:    #94A3B8;   /* secondary text           */
  --ghost:    #475569;   /* disabled / placeholder   */
}
```

### 2b. Typography
Pull from Google Fonts.

| Role             | Typeface         | Usage                                          |
|------------------|------------------|------------------------------------------------|
| Display / Hero   | Space Grotesk    | Page titles, big numbers, artist names         |
| Body             | Inter            | Descriptions, labels, button text              |
| Mono / Data      | JetBrains Mono   | Track IDs, dates, log output, JSON previews    |

Type scale: `11px / 13px / 15px / 18px / 24px / 32px / 48px / 64px`  
Line-heights: `1.2` for headings, `1.6` for body.  
Letter-spacing: `−0.02em` on display sizes, `0.08em` on all-caps labels.

### 2c. Shape & Motion

| Property         | Value                                              |
|------------------|----------------------------------------------------|
| Card radius      | `20px`                                             |
| Input radius     | `14px`                                             |
| Button radius    | `999px` (pill)                                     |
| Badge radius     | `999px`                                            |
| Modal radius     | `24px`                                             |
| Shadow (card)    | `0 0 0 1px var(--mist), 0 8px 32px rgba(0,0,0,.5)`|
| Glow (iris)      | `0 0 24px rgba(124,58,237,.35)`                    |
| Transition       | `all 200ms cubic-bezier(0.4, 0, 0.2, 1)`           |
| Framer spring    | `{ type: "spring", stiffness: 300, damping: 28 }`  |

**Glassmorphism rule:** Cards with album art behind them use  
`background: rgba(15,15,26,0.72); backdrop-filter: blur(20px) saturate(180%);`

---

## 3. Backend — `api.py` (FastAPI)

Create `api.py` in the same directory as `main.py`. Import all functions from `main.py` directly.

### Endpoints to implement

```
GET  /api/status          → { user: {display_name, id, images[]}, authenticated: bool }
GET  /api/artists         → { artists: [{id, name, images[], followers}], cached: bool }
DELETE /api/artists/cache → clears followed_artists_cache.json, returns { cleared: true }
POST /api/run             → starts the main pipeline (SSE stream)
GET  /api/runs/{id}       → stream of SSE events for a specific run
GET  /api/tracklists      → list all tracklist_*.json files in directory
GET  /api/tracklists/{filename} → returns the tracks array from that JSON
GET  /api/playlists       → last N playlists created (read from a runs.json log)
```

### POST /api/run body schema
```json
{
  "start": 1,
  "end": 9999,
  "cutoff": "2025-11-01",
  "verbose": false
}
```

### SSE event types (stream from `GET /api/runs/{id}`)
Emit newline-delimited `data: {json}\n\n` payloads:

```
{ "type": "start",     "total_artists": 142, "run_id": "abc123" }
{ "type": "artist",    "index": 1, "name": "Bonobo", "status": "processing" }
{ "type": "track",     "artist": "Bonobo", "track_name": "...", "album_type": "album" }
{ "type": "duplicate", "track_name": "...", "skipped_from": "..." }
{ "type": "done",      "total_tracks": 87, "duplicates_prevented": 12, "playlist_url": "..." }
{ "type": "error",     "message": "..." }
```

Use `asyncio` + `asyncio.Queue` so the SSE endpoint doesn't block.  
Inject a `run_id` UUID into each run; store progress in-memory dict `RUNS: dict[str, RunState]`.

---

## 4. Frontend Architecture

```
src/
  components/
    layout/     Sidebar, TopBar, PageShell
    ui/         Card, Badge, Button, Input, ProgressRing, Skeleton
    charts/     ReleasesTimeline, AlbumTypePie, CollabNetwork, ArtistBar
    track/      TrackRow, TrackCard, ArtworkBlur
    run/        RunConsole, ProgressOrb, ArtistQueue
  pages/
    Dashboard.jsx
    Artists.jsx
    Releases.jsx
    RunPage.jsx
    Playlists.jsx
  hooks/
    useSSE.js
    useRun.js
    useArtists.js
  lib/
    api.js      (fetch wrappers)
    colors.js   (extract dominant color from album art URL)
  App.jsx
  main.jsx
```

---

## 5. Pages & Components (detailed specs)

---

### 5a. Sidebar (persistent)

- **Width:** 220px, `background: var(--slate)`, left border `1px solid var(--mist)`
- **Logo area:** "WAVEFEED" in Space Grotesk 600, `color: var(--neon)`, with a geometric waveform SVG icon (3 vertical bars, rounded, different heights — like a mini equalizer)
- **Nav items:** Dashboard · Artists · Releases · Run · Playlists
- Active item: pill highlight `background: var(--iris-dim)`, left accent bar `3px var(--iris)`
- Bottom: user avatar (circle, 32px) + `display_name` + logout icon

---

### 5b. Dashboard Page

**Hero strip (full width, ~180px tall):**  
Background: horizontal gradient `var(--void) → var(--iris-dim) → var(--void)`.  
Left: "Good morning, {name}" in Space Grotesk 32px + subline "You follow **142** artists" in Inter 16px comet.  
Right: 3 stat blocks in a row:

```
[  87 tracks ]   [ 12 dupes stopped ]   [ 3 new releases ]
  New since        Signature dedup         Last 7 days
```
Each stat: number in Space Grotesk 40px `var(--snow)`, label in Inter 11px uppercase `var(--comet)`.

**Quick-run card:**  
A prominent card below the hero, `background: var(--obsidian)`, iris glow shadow.  
- `cutoff` date picker (styled, not native-looking)
- `start` and `end` number inputs
- A large pill button: "SCAN NEW RELEASES →" `background: var(--iris)`, hover scale `1.02`, active scale `0.98`
- Shows last run timestamp below the button in mono 12px comet

**Sparkline row (3 mini charts, ~120px tall each):**  
`ReleasesPerDay` (area chart, last 30 days), `AlbumTypeBreakdown` (donut), `TopArtistsByTracks` (horizontal bar).  
All share the same muted color palette: iris, mint, rose, sky, amber.

---

### 5c. Artists Page

**Header:** "Your Artists · {n} followed" + refresh cache button (icon only, with tooltip "Clear cache & refetch")  
**Search bar:** full-width, rounded pill, ghost border on focus becomes iris.

**Grid:** `auto-fill, minmax(160px, 1fr)` artist cards.  
Each card:
- Square top half: artist image (object-cover), fallback = initials on iris gradient
- Rounded corners `20px`
- On hover: image scales `1.08` (overflow hidden on card), subtle iris glow appears
- Name in Space Grotesk 15px
- Follower count in Inter 11px comet mono
- "New" badge (mint, pill) if the artist appeared in the last run

**Skeleton loading:** shimmer animation on placeholder cards while `/api/artists` loads.

---

### 5d. Releases Page

**Toolbar:** filter pills for album type — All · Album · Single · EP · Featured  
Each pill is a toggle button; active = iris fill.  
Sort by: Release Date (default) | Artist | Album Type

**Track list:**  
Full-bleed dark table, no outer border.  
Each row (`TrackRow`):
```
[artwork 48px]  [track name + album name subline]  [artist]  [badge]  [date]  [role icon]  [⋯]
```
- `artwork`: 48×48 rounded-12 image; on hover, expand to show a 200px floating preview card with color-extracted bg
- `track name`: Snow 15px, album name below in Comet 12px mono
- `badge`: colored pill — "album" (iris), "single" (sky), "ep" (amber), "featured" (rose)
- `date`: mono 13px comet
- `role icon`: mic icon (main artist) or link-2 icon (featured)
- `⋯` menu: Open in Spotify · Copy Spotify URI

Virtualize rows with `react-window` if track count > 200.

---

### 5e. Run Page (the marquee screen)

This is where visualization is king. Split into three columns:

**Left column — Controls (240px):**
- `start` / `end` inputs
- `cutoff` date picker
- verbose toggle
- "START RUN" pill button (iris, with play icon)
- "STOP" button appears once run starts (rose outline pill)

**Center column — Live feed (flex-1):**  
`RunConsole` component: a log-like feed that animates in each SSE event as a row.

Event styling:
- `artist` → row: faint top border, left iris accent bar, artist name in Snow, "Processing…" in Comet
- `track` → row: 4px left indent, mint dot, track name + album badge in a single line
- `duplicate` → row: ghost color, strikethrough on track name, "↳ skipped" in ghost mono
- `error` → row: rose left border, rose text
- `done` → big centered block: "✓ Run complete" in mint 24px, stats below

Each row slides in from the left with `Framer Motion` `initial={{ x: -16, opacity: 0 }} animate={{ x: 0, opacity: 1 }}`.

**Right column — Stats panel (280px):**  
Live-updating as SSE events come in.

`ProgressOrb`:  
A large (160px) circular SVG progress ring. 
- Outer ring: `var(--mist)` stroke 6px
- Progress arc: gradient from `var(--iris)` to `var(--neon)`, stroke 6px, `stroke-linecap: round`
- Center: `{processed} / {total}` in Space Grotesk 24px + "artists" in Inter 12px comet
- Orbiting dot at the arc tip: 8px circle, iris, drop-shadow glow

`ArtistQueue`:  
A mini list of the 5 most recently processed artists, each sliding in from bottom.  
Shows name + "3 tracks found" or "no new releases" in comet 12px.

Real-time counters (updating live via SSE):
```
[  87 ]   Tracks found
[  12 ]   Dupes blocked
[   5 ]   Collaborations
[   2 ]   Errors
```
Each number increments with a brief scale-up animation on change.

`AlbumTypeDonut` (live):
A recharts `PieChart` that updates as each track event arrives.
Colors: album=iris, single=sky, ep=amber, featured=rose.
Center label: total track count.

---

### 5f. Playlists Page

List of created playlists (read from runs log). Each card:
- Playlist name (Space Grotesk 18px)
- Timestamp + artist range used (e.g. "Artists 1–142")
- Track count badge (iris pill)
- "Open in Spotify" button (mint outline pill, external link icon)
- Small row of up to 8 album artwork thumbnails (overlapping, like AvatarGroup)

---

## 6. Visualisation Components (detailed)

All charts: `background: transparent`, no axis lines (just subtle grid), tooltips styled with `var(--obsidian)` bg + `var(--mist)` border + Snow text.

### 6a. ReleasesTimeline (area chart)
- X: dates (last 30 days, or range of current run results)
- Y: track count per day
- Area fill: gradient from `rgba(124,58,237,0.3)` at bottom → `rgba(124,58,237,0)` at baseline
- Stroke: `var(--neon)` 2px, smooth curve
- Dot on hover: 6px iris circle + tooltip showing "3 tracks · Nov 14"
- Animate on mount: `isAnimationActive` + stroke-dashoffset reveal

### 6b. AlbumTypeDonut (pie chart)
- Donut with `innerRadius=60%`
- Segments: iris / sky / amber / rose
- On hover: segment lifts `outerRadius + 8px`, tooltip appears
- Center label: "87 tracks" in Space Grotesk
- Legend: horizontal pill row below the chart

### 6c. TopArtistsByTracks (horizontal bar)
- Top 10 artists by new track count, sorted descending
- Bars: rounded right end (radius 6px), iris gradient left→neon right
- Artist name left-aligned in Inter 13px Snow
- Count right-aligned in mono 12px neon
- Bars animate width from 0 on mount

### 6d. CollabNetwork (D3 force-directed graph)
- Available on the Releases page, behind a "Show collab graph" toggle button
- Nodes: artists (circle, sized by track count)
  - Followed artist nodes: filled iris
  - Collaboration partner nodes: outline rose, smaller
- Edges: thin `var(--mist)` lines, opacity 0.5
- On hover node: shows artist name tooltip + highlights all edges to that node in neon
- Drag nodes to reposition
- Zoom + pan enabled
- Render only if ≥ 2 collaboration tracks exist

---

## 7. ArtworkBlur — signature component

This is the page's memorable design element: when a track or album is "in focus" (hovered in Releases, or the current artist processing in RunPage), its album artwork is extracted for dominant color and used as a diffused, blurred background wash behind the entire panel it lives in.

Implementation:
1. `colors.js`: use a `<canvas>` to sample the center 10×10px of the artwork image, average the RGB, return as hex.
2. Apply as `box-shadow: inset 0 0 80px 40px {dominantColor}33` on the parent card or panel.
3. Transition: `transition: box-shadow 600ms ease`.
4. Fallback: iris glow.

---

## 8. Micro-interactions & Polish

- **Button press:** `scale(0.96)` on `:active`, spring back
- **Card hover:** `translateY(-3px)` + shadow intensifies
- **Badge appear:** `scale(0) → scale(1)` with spring, 200ms
- **Number counter:** when a stat number increments, use a brief `scale(1.2)` flash on the digit
- **Sidebar active change:** iris pill slides between nav items (absolute positioned, Framer Motion layout animation)
- **Page transitions:** `Framer Motion AnimatePresence`, `opacity 0→1 + y 12→0` in 200ms
- **Skeleton shimmer:** `background: linear-gradient(90deg, var(--obsidian), var(--mist), var(--obsidian))`, `background-size: 200%`, `animation: shimmer 1.6s infinite`
- **Run console new row:** enter from left (`x: -16, opacity: 0`) over 160ms
- **Error state:** component briefly flashes rose background, then settles

---

## 9. TypeScript Interfaces

```ts
interface Artist {
  id: string;
  name: string;
  images: { url: string; width: number; height: number }[];
  followers: { total: number };
}

interface Track {
  track_id: string;
  track_name: string;
  album_name: string;
  album_type: 'album' | 'single' | 'ep' | 'compilation' | 'unknown';
  release_date: string;          // "YYYY-MM-DD" or "YYYY-MM" or "YYYY"
  artist_name: string;
  performer_role: 'main' | 'featured' | 'unknown';
  is_collaboration: boolean;
  all_artists: string[];
  main_artist?: string;          // only when is_collaboration === true
  has_artwork: boolean;
  album_artwork_url?: string;
  track_signature: string;
}

interface RunEvent {
  type: 'start' | 'artist' | 'track' | 'duplicate' | 'done' | 'error';
  run_id?: string;
  total_artists?: number;
  index?: number;
  name?: string;
  status?: string;
  track_name?: string;
  album_type?: string;
  artist?: string;
  skipped_from?: string;
  total_tracks?: number;
  duplicates_prevented?: number;
  playlist_url?: string;
  message?: string;
}

interface RunState {
  id: string;
  started_at: string;
  config: { start: number; end: number; cutoff: string };
  events: RunEvent[];
  status: 'running' | 'done' | 'error';
  tracks_found: number;
  duplicates_blocked: number;
  artists_processed: number;
  total_artists: number;
  playlist_url?: string;
}
```

---

## 10. Implementation Notes

1. **CORS:** add `fastapi.middleware.cors` allowing `http://localhost:5173`
2. **SSE:** use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"` and `X-Accel-Buffering: no` header
3. **Auth guard:** on app load, hit `/api/status`. If 401, show a centered "Connect Spotify" card with the OAuth redirect URL and the Spotify green #1DB954 as the only color on that screen.
4. **env file:** read `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI` from `.env` via `python-dotenv` (already in `main.py`)
5. **Vite proxy:** proxy `/api` to `http://localhost:8000` in `vite.config.js` to avoid CORS in dev
6. **No native form elements:** all inputs are custom-styled `<input>` tags, never bare `<form>` elements with default browser styling
7. **Fonts:** load via `@import` in `index.css` from `fonts.googleapis.com` — Space Grotesk (300,400,600,700), Inter (400,500,600), JetBrains Mono (400,500)
8. **Recharts responsiveness:** always wrap charts in `<ResponsiveContainer width="100%" height={height}>`
9. **react-window:** use `FixedSizeList` for the track table; row height 64px
10. **D3 collab graph:** mount into a `useRef` canvas element; clean up simulation on unmount

---

## 11. File Scaffold to Generate

Generate these files (in order):

1. `api.py` — FastAPI server
2. `package.json` — deps: react, react-dom, vite, tailwindcss, framer-motion, recharts, d3, react-window, lucide-react
3. `vite.config.js`
4. `tailwind.config.js` — extend colors with all CSS vars
5. `src/index.css` — font imports + `:root` tokens + base resets
6. `src/lib/api.js`
7. `src/lib/colors.js`
8. `src/hooks/useSSE.js`
9. `src/hooks/useRun.js`
10. `src/components/ui/` — Card, Badge, Button, Input, ProgressRing, Skeleton
11. `src/components/layout/` — Sidebar, TopBar, PageShell
12. `src/components/charts/` — ReleasesTimeline, AlbumTypePie, CollabNetwork, ArtistBar
13. `src/components/track/` — TrackRow, TrackCard, ArtworkBlur
14. `src/components/run/` — RunConsole, ProgressOrb, ArtistQueue
15. `src/pages/` — Dashboard, Artists, Releases, RunPage, Playlists
16. `src/App.jsx`
17. `src/main.jsx`

---

## 12. Acceptance Criteria

- [ ] `python api.py` starts with no errors; Spotify auth works
- [ ] Dashboard loads in < 1s (artists from cache)
- [ ] Run page streams events live; console rows animate in
- [ ] ProgressOrb ring animates correctly 0 → 100%
- [ ] ArtworkBlur changes color wash when hovering different tracks
- [ ] CollabNetwork renders and is draggable
- [ ] AlbumTypeDonut updates in real-time during a run
- [ ] All pills/badges use correct semantic colors (album=iris, single=sky, ep=amber, featured=rose)
- [ ] No layout shift on page transitions
- [ ] Works at 1280px, 1440px, and 1920px widths
