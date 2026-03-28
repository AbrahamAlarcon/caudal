# SNIA BNA reportes — browser download helper

`snia_reportes_download.py` automates part of the workflow on the official DGA portal:

**https://snia.mop.gob.cl/BNAConsultas/reportes**

It launches Chrome, can fill filters (optional **preset**), waits for you to solve **reCAPTCHA**, runs search, selects stations, fills dates, and clicks **Generar XLS**. Excel files land in the folder you choose (default: `snia_downloads` next to this script).

> **reCAPTCHA** must be solved manually in the browser; the script does not bypass it.

---

## Requirements

- **Python 3.9+** (recommended)
- **Google Chrome** installed
- **Selenium 4.6+** (Selenium manages ChromeDriver)

```bash
pip install "selenium>=4.15.0"
```

---

## Quick start (recommended)

Use a **real terminal** (not only an IDE debug console) if you want `input()` and **Enter** to work reliably:

```bash
cd /path/to/caudal/frommopversion
python3 snia_reportes_download.py --preset rinihue-precip-valdivia
```

1. The script sets meteorological report, daily precipitation, Los Ríos region, Valdivia basin, and two Lago Riñihue stations.
2. Complete **reCAPTCHA** when the script indicates.
3. It prompts for a **year (YYYY)**; it fills **01/01/year** → **31/12/year** and downloads the Excel.
4. It asks whether you want **another year** (`s` / `N`).

Custom download folder:

```bash
python3 snia_reportes_download.py --preset rinihue-precip-valdivia -d ~/Downloads/snia_mop
```

`-d` / `--download-dir` accepts absolute paths, relative paths, or `~`. The folder is **created** if missing.

---

## Date range mode (no interactive year loop)

```bash
python3 snia_reportes_download.py --preset rinihue-precip-valdivia --no-interactive-years \
  --fecha-inicio 01-01-2020 --fecha-fin 31-12-2024
```

The site limits long spans; the script splits into chunks of up to **four years**.

Accepted date formats: `dd/mm/yyyy`, `dd-MM-yyyy`, `yyyy-mm-dd`.

---

## No preset (manual form in the browser)

```bash
python3 snia_reportes_download.py -d ~/Downloads/snia_mop
```

You configure report type, stations, and reCAPTCHA in Chrome; the script waits until **Generar XLS** is available, then continues with the interactive year loop or the CLI date range, depending on flags.

---

## Main options

| Option | Description |
|--------|-------------|
| `--preset rinihue-precip-valdivia` | Fills the form (meteo, daily precip., Los Ríos, Valdivia basin, two Riñihue stations). |
| `-d DIR`, `--download-dir DIR` | Where Chrome saves Excel files (default: `snia_downloads` here). |
| `--no-interactive-years` | Use `--fecha-inicio` / `--fecha-fin` instead of prompting for a year. |
| `--wait-after-download N` | **Maximum** seconds after «Generar XLS» (default 120). Detects new files in the folder; on macOS/Linux you can press **Enter** in the terminal when the download finishes. |
| `--interactive-captcha-wait-s N` | Max seconds per interactive reCAPTCHA / page-ready wait (default 300). On Unix, **Enter** forces an immediate check. |
| `--captcha-wait-s N` | With `--preset` and **without** interactive years: wait for «Buscar» (default 600 s). |
| `--region-value`, `--cuenca-partial` | Override preset region / partial basin text. |
| `-v`, `--verbose` | DEBUG logging. |

Full list:

```bash
python3 snia_reportes_download.py --help
```

---

## Flow (with preset)

1. Open reportes URL.
2. Preset: meteorological accordion, daily precipitation, region, basin, search mode.
3. Wait until **Buscar** is enabled (after reCAPTCHA).
4. Click **Buscar** and select stations in the list.
5. Loop: interactive year **or** CLI date chunks → fill dates → **Generar XLS** → wait for download (folder scan + optional Enter) → next chunk/year.

---

## Troubleshooting

- **Looks stuck**: Often reCAPTCHA, the site’s “please wait” panel, or the post-download wait. Watch log lines every ~10 s; on Unix, **Enter** can trigger an early re-check.
- **No year prompt**: Do not pass `--no-interactive-years` if you want the default year loop.
- **Excel not in the folder**: Confirm Chrome is using the same path as `-d`; if Chrome’s default download folder differs, point `-d` there or change Chrome’s download location.
- **stdin / year not read**: Run from **Terminal**; some IDE consoles do not attach stdin to `input()`.
- **Second year / popup errors**: Use the current `snia_reportes_download.py` (stale-element fixes for popup close after repeated **Generar XLS**).

---

## Reference

- Portal: [SNIA BNA Consultas — reportes](https://snia.mop.gob.cl/BNAConsultas/reportes)
- Evolved from the approach in `fromdag/original.py` (Tkinter + Windows); this version is a cross-platform CLI.
