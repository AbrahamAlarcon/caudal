# SNIA BNA reportes — browser download helper

`snia_reportes_download.py` automates part of the workflow on the official DGA portal:

**https://snia.mop.gob.cl/BNAConsultas/reportes**

It launches **Google Chrome** under Selenium’s control, points downloads at a folder you choose (default: `snia_downloads` next to this script), and drives the report form where the site allows it. **reCAPTCHA** and any blocking screens are still **your** responsibility in the browser.

> **reCAPTCHA** must be solved manually; the script does not bypass it.

---

## How it works

1. **Browser session** — Selenium starts Chrome with download preferences so files go to `-d` / `--download-dir`. The script opens the SNIA reportes URL and keeps the same session for the whole run.

2. **Form automation (optional)** — With `--preset rinihue-precip-valdivia`, the script opens the right report type (meteorological → daily precipitation), selects region (Los Ríos), basin (Valdivia), triggers **Buscar**, and ticks the configured stations (e.g. Lago Riñihue meteo + control). Without a preset, you complete the form yourself in Chrome.

3. **Readiness waits** — Before sensitive steps, the script polls until the page is ready (e.g. **Buscar** or **Generar XLS** enabled). In **interactive** mode it logs progress about every 10 seconds and, on macOS/Linux, treats **Enter** in the terminal as “check again now” instead of waiting for the full timeout.

4. **Dates and download** — For each **chunk** of dates (in interactive-by-year mode, one chunk per calendar year: 01/01/YYYY–31/12/YYYY), the script fills the **desde** / **hasta** fields, clicks **Generar XLS**, then either:
   - waits for a new/changed file in the download folder (with a **maximum** wait, default 120 s), again allowing **Enter** to re-check early on Unix; or  
   - detects the SNIA **info popup** (e.g. no records for that period), **prints the portal message** to the console and log, closes the popup, clears the date fields using **fresh** DOM lookups (avoids stale-element crashes), and moves on without treating it as a file download.

5. **Interactive year loop (default)** — After setup, the script repeatedly asks in the terminal which **year** to download, runs one full-year chunk, then asks if you want **another year**. An **empty** year input exits the loop. This is the default; use `--no-interactive-years` to switch to a single CLI date range instead.

6. **Non-interactive range** — With `--no-interactive-years` and `--fecha-inicio` / `--fecha-fin`, the script computes **up to four-year** segments (portal limitation) and processes them in sequence without asking for a year each time.

---

## Requirements

- **Python 3.9+** (recommended)
- **Google Chrome** installed
- **Selenium 4.6+** (Selenium manages ChromeDriver)

```bash
pip install "selenium>=4.15.0"
```

---

## Interactive mode (default)

**Interactive mode** means: the script **asks you for a year** on the terminal, downloads that full calendar year, then asks whether to do **another year**. You do **not** pass `--no-interactive-years`.

### Why use a real terminal?

The script uses Python `input()` for the year and yes/no prompts, and on macOS/Linux it can read **Enter** during waits. **IDE “Run” panels** often have no real stdin—use **Terminal.app**, **iTerm**, or an integrated terminal that is attached to your shell.

### Command

```bash
cd /path/to/caudal/frommopversion
python3 snia_reportes_download.py --preset rinihue-precip-valdivia
```

Optional: put Excel files somewhere explicit:

```bash
python3 snia_reportes_download.py --preset rinihue-precip-valdivia -d ~/Downloads/snia_mop
```

`-d` / `--download-dir` accepts absolute paths, relative paths, or `~`; the folder is **created** if missing.

### Step-by-step (typical run with preset)

1. **Chrome opens** on the SNIA reportes page; the preset fills report type, region, basin, and related controls.

2. **First reCAPTCHA wait** — Solve reCAPTCHA in the browser so **Buscar** becomes usable. The script waits (default up to **300 s** per wait; tune with `--interactive-captcha-wait-s`). If it seems idle, read the INFO lines; on Unix you can press **Enter** to force an immediate re-check.

3. **Buscar and stations** — The script clicks **Buscar** and selects the preset stations in the table.

4. **Optional wait before downloads** — If the script needs **Generar XLS** to be ready, it waits again (same style: periodic messages, **Enter** on Unix).

5. **Year prompt** — Terminal shows something like: *¿Qué año descargar? (YYYY). Enter vacío para terminar:*  
   - Enter a four-digit year (e.g. `2023`).  
   - **Empty Enter** ends the download loop and the script will close the browser after cleanup.

6. **Per year** — For that year it sets **01/01/YYYY**–**31/12/YYYY**, clicks **Generar XLS**, then:
   - **If a file downloads** — It watches the download folder until a new file appears or the max wait elapses (`--wait-after-download`, default 120 s). **Enter** (Unix) can shorten the wait once you see the file.
   - **If the portal shows a popup** (e.g. no data) — The message is printed in a framed block on **stderr**, the popup is closed, dates are cleared safely, and the script continues **without** crashing.

7. **Another year?** — Terminal asks: *¿Quieres descargar otro año? [s/N]:*  
   - Answer `s`, `si`, `sí`, `y`, or `yes` to go back to step 5.  
   - Anything else (or just Enter) stops the year loop.

8. **Exit** — The browser is closed; check your download folder.

### Tuning interactive waits

| Flag | Role in interactive mode |
|------|---------------------------|
| `--interactive-captcha-wait-s N` | Max seconds **per** wait for reCAPTCHA / page ready (default 300). |
| `--wait-after-download N` | Max seconds after **Generar XLS** while looking for a new file (default 120). |
| `-v` / `--verbose` | DEBUG logging (Selenium steps, download folder detail). |

---

## Date range mode (not interactive years)

Skip the year prompts and use a fixed range (auto-split into ≤4-year chunks):

```bash
python3 snia_reportes_download.py --preset rinihue-precip-valdivia --no-interactive-years \
  --fecha-inicio 01-01-2020 --fecha-fin 31-12-2024
```

Accepted date formats: `dd/mm/yyyy`, `dd-MM-yyyy`, `yyyy-mm-dd`.

With `--preset` and `--no-interactive-years`, `--captcha-wait-s` controls how long to wait for **Buscar** after reCAPTCHA (default 600 s).

---

## No preset (manual form in the browser)

```bash
python3 snia_reportes_download.py -d ~/Downloads/snia_mop
```

You choose report, stations, and reCAPTCHA in Chrome. The script waits until **Generar XLS** is available, then runs either the **interactive year** loop (default) or the CLI range if you passed `--no-interactive-years`.

---

## Main options (summary)

| Option | Description |
|--------|-------------|
| `--preset rinihue-precip-valdivia` | Fills meteo daily precip., Los Ríos, Valdivia basin, two Riñihue stations. |
| `-d DIR`, `--download-dir DIR` | Chrome download directory (default: `snia_downloads` here). |
| `--no-interactive-years` | Use `--fecha-inicio` / `--fecha-fin` instead of the year loop. |
| `--wait-after-download N` | Max seconds after «Generar XLS» (default 120); folder scan + optional **Enter** on Unix. |
| `--interactive-captcha-wait-s N` | Max seconds per interactive readiness wait (default 300). |
| `--captcha-wait-s N` | With `--preset` and **without** interactive years: wait for **Buscar** (default 600 s). |
| `--region-value`, `--cuenca-partial` | Override preset region / basin partial text. |
| `-v`, `--verbose` | DEBUG logging. |

Full list:

```bash
python3 snia_reportes_download.py --help
```

---

## Troubleshooting

- **Looks stuck** — Often reCAPTCHA, the site’s “please wait” panel, or post-download wait. Watch INFO lines (~every 10 s); on Unix, **Enter** triggers an early re-check.
- **No year prompt** — You passed `--no-interactive-years`. Omit it for interactive years.
- **Excel not in the folder** — Chrome must use the same path as `-d`.
- **stdin / prompts ignored** — Run from a real terminal, not a broken stdin in the IDE.
- **“No records” popup** — Normal for some years; the script prints the portal text and can continue to the next year if you choose **s** on *¿Quieres descargar otro año?*

---

## Reference

- Portal: [SNIA BNA Consultas — reportes](https://snia.mop.gob.cl/BNAConsultas/reportes)
- Evolved from `fromdag/original.py` (Tkinter + Windows); this version is a cross-platform CLI.
