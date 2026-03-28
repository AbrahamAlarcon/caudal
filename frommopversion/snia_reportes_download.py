#!/usr/bin/env python3
"""
Versión mejorada (CLI) del asistente SNIA BNA reportes.

Basada en la idea de fromdag/original.py: abre
https://snia.mop.gob.cl/BNAConsultas/reportes, el usuario resuelve reCAPTCHA;
este script puede rellenar parte del formulario (--preset), marcar estaciones,
rellenar fechas y pedir los Excel en bloques de hasta 4 años.

Mejoras respecto a original.py:
  - Sin Tkinter: se ejecuta con ``python snia_reportes_download.py``.
  - ChromeDriver vía Selenium 4.6+ (sin ruta fija a .exe de Windows).
  - Opción ``--preset rinihue-precip-valdivia``: meteorológico, precipitaciones diarias,
    Los Ríos, cuenca Valdivia, y dos estaciones Lago Riñihue (reCAPTCHA sigue siendo manual).
  - Carpeta de descargas configurable.
  - Rango de fechas recortado correctamente al periodo pedido (no solo años enteros).
  - Manejo del popup informativo sin TimeoutException cuando la descarga sí ocurre.

Uso típico:
  python snia_reportes_download.py --preset rinihue-precip-valdivia
  # Por defecto pregunta por consola el año (01/01/año–31/12/año), luego si quieres otro año.

  python snia_reportes_download.py --preset rinihue-precip-valdivia --no-interactive-years \\
      --fecha-inicio 01-01-2020 --fecha-fin 27-03-2026
  python snia_reportes_download.py -v

  python snia_reportes_download.py --preset rinihue-precip-valdivia -d ~/Downloads/snia_mop
  # Carpeta de Excel: -d o --download-dir (ruta absoluta, relativa o ~/…; se crea si no existe)

Por defecto el script **pregunta el año** en consola, usa **01/01/año** y **31/12/año**, descarga
y pregunta si quieres otro año. Usa ``--no-interactive-years`` para un solo rango con
``--fecha-inicio`` / ``--fecha-fin`` (tramos de hasta 4 años). En cada espera de reCAPTCHA
hay hasta ~5 min o Enter en consola.

Si «parece colgado»: suele ser espera de reCAPTCHA, panel «Por favor espere» del sitio,
``--wait-after-download`` (30 s por Excel), o ``input()`` esperando que escribas el año
(ejecuta en una terminal real, no solo el panel de depuración sin stdin).
"""

from __future__ import annotations

import argparse
from typing import Any, Union
import datetime as dt
import logging
import os
import select
import sys
import time
import unicodedata

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

SNIA_REPORTES_URL = "https://snia.mop.gob.cl/BNAConsultas/reportes"

# Valores del <select id="filtroscirhform:region"> (snapshot portal SNIA).
REGION_DE_LOS_RIOS_VALUE = "14"

# Si el usuario pasa texto en lugar del value numérico del <option>.
_REGION_FOLD_TO_VALUE: dict[str, str] = {
    "DELOSRÍOS": "14",
    "DELOSRIOS": "14",
    "LOSRIOS": "14",
    "REGIONDELOSRÍOS": "14",
    "REGIONDELOSRIOS": "14",
}

FORM_PRESETS: dict[str, dict] = {
    "rinihue-precip-valdivia": {
        "region_value": REGION_DE_LOS_RIOS_VALUE,
        "cuenca_partial": "Valdivia",
        # Lista: cadenas (todas deben aparecer) o dict con include / exclude / require_any.
        "station_matchers": [
            ["LAGO", "RIÑIHUE", "METEO"],
            {
                "include": ["LAGO", "RIÑIHUE"],
                "exclude": ["METEO"],
                "require_any": ["CONTROL", "ESTACION", "ESTACI"],
            },
        ],
    },
}

log = logging.getLogger(__name__)


class FormAutomationError(Exception):
    """Fallo al localizar controles del formulario SNIA (IDs o texto distintos al esperado)."""


def fold_ascii_upper(s: str) -> str:
    """Comparación tolerante (mayúsculas, sin tildes)."""
    nfd = unicodedata.normalize("NFD", s)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return stripped.upper()


def fold_station_text(s: str) -> str:
    """Como fold_ascii_upper pero unifica Ñ→N para coincidir Riñihue / RINIHUE en tablas DGA."""
    return fold_ascii_upper(s).replace("Ñ", "N")


def _normalize_station_pick(pick: Union[list[str], dict[str, Any]]) -> dict[str, Any]:
    if isinstance(pick, dict):
        return {
            "include": list(pick["include"]),
            "exclude": list(pick.get("exclude", [])),
            "require_any": pick.get("require_any"),
        }
    return {"include": list(pick), "exclude": [], "require_any": None}


def _row_matches_station_spec(rt: str, spec: dict[str, Any]) -> bool:
    f = fold_station_text(rt)
    for ex in spec["exclude"]:
        if fold_station_text(ex) in f:
            return False
    for inc in spec["include"]:
        if fold_station_text(inc) not in f:
            return False
    req = spec["require_any"]
    if req:
        if not any(fold_station_text(a) in f for a in req):
            return False
    return True


def _click_station_checkbox(driver: webdriver.Chrome, row) -> None:
    """Localiza checkboxes en la fila y marca el primero visible (clic + refuerzo JS)."""
    boxes = row.find_elements(By.XPATH, ".//input[@type='checkbox']")
    if not boxes:
        raise NoSuchElementException("sin checkbox en la fila")
    for cb in boxes:
        try:
            if not cb.is_displayed():
                continue
        except StaleElementReferenceException:
            continue
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cb)
        if not cb.is_selected():
            try:
                cb.click()
            except (ElementClickInterceptedException, StaleElementReferenceException):
                driver.execute_script("arguments[0].click();", cb)
        if not cb.is_selected():
            driver.execute_script(
                "arguments[0].checked = true;"
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));"
                "arguments[0].dispatchEvent(new Event('click', {bubbles: true}));",
                cb,
            )
        time.sleep(0.25)
        try:
            if cb.is_selected():
                return
        except StaleElementReferenceException:
            return
    raise NoSuchElementException("ningún checkbox visible o marcar en la fila")


def click_accordion_header(driver: webdriver.Chrome, title: str, timeout: int = 90) -> None:
    """Abre una categoría en «Tipos de Informe» (RichFaces accordion) por texto visible."""
    if "'" in title:
        raise ValueError("El título del acordeón no puede contener apóstrofo (XPath).")
    xp = (
        "//div[contains(@class,'rf-ac-itm-hdr')]"
        f"[.//div[contains(normalize-space(.), '{title}')]]"
    )
    hdr = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", hdr)
    time.sleep(0.2)
    hdr.click()
    log.info("Acordeón abierto: %s", title)


def check_report_checkbox_by_label(
    driver: webdriver.Chrome, label_contains: str, timeout: int = 90
) -> None:
    """Marca un tipo de informe por el texto del <label> de su fila."""
    xp = (
        "//tr[.//label[contains(., "
        + repr(label_contains)
        + ")]]//input[@type='checkbox']"
    )
    cb = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cb)
    if not cb.is_selected():
        cb.click()
        log.info("Marcado informe: %s", label_contains)
    else:
        log.info("Ya estaba marcado: %s", label_contains)


def _richfaces_panel_idle(driver: webdriver.Chrome) -> bool:
    """True si el waitPanel de RichFaces parece inactivo (no bloquea la UI)."""
    try:
        wp = driver.find_element(By.ID, "waitPanel")
        st = (wp.get_attribute("style") or "").replace(" ", "").lower()
        if "visibility:hidden" in st or "display:none" in st or "opacity:0" in st:
            return True
        try:
            if not wp.is_displayed():
                return True
        except StaleElementReferenceException:
            return True
        return False
    except NoSuchElementException:
        return True
    except StaleElementReferenceException:
        return True


def wait_richfaces_idle(driver: webdriver.Chrome, timeout: int = 120) -> None:
    """
    Espera a que el waitPanel no bloquee (evita clics perdidos).

    Antes usábamos solo WebDriverWait sin mensajes: hasta 120 s en silencio parecía
    un «cuelgue». Ahora hay logs cada ~10 s.
    """
    log.info(
        "Esperando fin de carga AJAX del portal (waitPanel, máx. %d s; no detiene el script)…",
        timeout,
    )
    deadline = time.monotonic() + timeout
    last_log = 0.0
    while time.monotonic() < deadline:
        if _richfaces_panel_idle(driver):
            return
        now = time.monotonic()
        if now - last_log >= 10:
            log.info(
                "Panel «Por favor espere…» aún activo (~%.0f s hasta timeout).",
                deadline - now,
            )
            last_log = now
        time.sleep(0.35)
    raise TimeoutException(
        f"waitPanel no quedó inactivo en {timeout} s. Prueba recargar la página en Chrome."
    )


def select_region(
    driver: webdriver.Chrome,
    region_spec: str,
    timeout: int = 90,
) -> None:
    """
    Elige región en filtroscirhform:region.

    ``region_spec`` puede ser:
    - El **value** del <option> (recomendado), p. ej. ``"14"`` para DE LOS RIOS.
    - Texto que aparezca en la opción, p. ej. ``"DE LOS RIOS"`` o ``"Los Ríos"``
      (se busca por coincidencia sin tildes).

    ``select_by_value("DE LOS RIOS")`` **falla** porque el value real es ``14``, no el texto;
    ese era un error frecuente.
    """
    wait_richfaces_idle(driver, timeout)
    sel_el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.ID, "filtroscirhform:region"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sel_el)
    dd = Select(sel_el)
    spec = region_spec.strip()
    chosen = False

    if spec.isdigit():
        dd.select_by_value(spec)
        chosen = True
        log.info("Región por value numérico: %s", spec)
    else:
        key = fold_ascii_upper(spec).replace(" ", "")
        if key in _REGION_FOLD_TO_VALUE:
            dd.select_by_value(_REGION_FOLD_TO_VALUE[key])
            chosen = True
            log.info(
                "Región por alias %r → value=%s",
                spec,
                _REGION_FOLD_TO_VALUE[key],
            )

    if not chosen:
        needle = fold_ascii_upper(spec)
        for opt in dd.options:
            val = opt.get_attribute("value") or ""
            if not val.strip():
                continue
            if needle in fold_ascii_upper(opt.text):
                dd.select_by_visible_text(opt.text)
                chosen = True
                log.info("Región por texto de opción: %s (value=%s)", opt.text.strip(), val)
                break

    if not chosen:
        opts = [(o.get_attribute("value"), o.text.strip()) for o in dd.options if o.text.strip()]
        raise FormAutomationError(
            f"No se pudo elegir región {region_spec!r}. "
            f"Usa el value numérico (p. ej. 14 para Los Ríos) o un fragmento del texto. "
            f"Opciones (value, texto): {opts[:8]}…"
        )

    wait_richfaces_idle(driver, timeout)
    sel_el = driver.find_element(By.ID, "filtroscirhform:region")
    dd = Select(sel_el)
    opt = dd.first_selected_option
    log.info(
        "Región efectiva en el <select>: value=%s texto=%r",
        opt.get_attribute("value"),
        opt.text.strip(),
    )
    time.sleep(0.8)


def ensure_busqueda_cuenca_o_nombre(driver: webdriver.Chrome) -> None:
    """Modo «Cuenca Hidrográfica o Nombre Estación»."""
    rid = "filtroscirhform:selectBusqForEstacion:0"
    radio = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, rid)))
    if not radio.is_selected():
        radio.click()
        log.info("Activado «Cuenca Hidrográfica o Nombre Estación».")
        time.sleep(1.0)
    else:
        log.debug("Ya activo «Cuenca Hidrográfica o Nombre Estación».")


def find_cuenca_select(driver: webdriver.Chrome):
    """El segundo <select class='select-filtro'> (no el de región)."""
    for sel in driver.find_elements(By.CSS_SELECTOR, "select.select-filtro"):
        eid = sel.get_attribute("id") or ""
        if eid == "filtroscirhform:region":
            continue
        if sel.is_displayed():
            return sel
    return None


def select_cuenca_by_partial_text(
    driver: webdriver.Chrome, partial: str, timeout: int = 90
) -> None:
    needle = fold_ascii_upper(partial)

    def cuenca_ready(d: webdriver.Chrome):
        s = find_cuenca_select(d)
        if s is None:
            return False
        opts = [o.text for o in Select(s).options if o.text.strip()]
        return len(opts) > 1

    WebDriverWait(driver, timeout).until(cuenca_ready)
    sel_el = find_cuenca_select(driver)
    if sel_el is None:
        raise FormAutomationError("No se encontró el desplegable de cuenca hidrográfica.")

    dd = Select(sel_el)
    for opt in dd.options:
        if needle in fold_ascii_upper(opt.text):
            dd.select_by_visible_text(opt.text)
            log.info("Cuenca seleccionada: %s", opt.text.strip())
            time.sleep(1.0)
            return
    opts = [o.text.strip() for o in dd.options]
    raise ValueError(
        f"No hay opción de cuenca que contenga {partial!r}. Opciones: {opts[:25]}…"
    )


def _buscar_is_enabled(driver: webdriver.Chrome) -> bool:
    try:
        btn = driver.find_element(By.ID, "filtroscirhform:buscar")
        return bool(btn.is_enabled())
    except NoSuchElementException:
        return False


def _generar_xls_is_ready(driver: webdriver.Chrome) -> bool:
    """Listo para pedir Excel (fechas + botón habilitado)."""
    try:
        g = driver.find_element(By.NAME, "filtroscirhform:generarxls")
        return bool(g.is_enabled())
    except NoSuchElementException:
        return False


def wait_for_buscar_enabled(driver: webdriver.Chrome, timeout_s: int = 600) -> None:
    """Tras reCAPTCHA el botón Buscar se habilita."""
    log.info(
        "Esperando a que «Buscar» quede habilitado (reCAPTCHA). Tiempo máx. %d s…",
        timeout_s,
    )
    end = time.monotonic() + timeout_s
    last_log = 0.0
    while time.monotonic() < end:
        if _buscar_is_enabled(driver):
            log.info("Botón «Buscar» habilitado.")
            return
        now = time.monotonic()
        if now - last_log >= 30:
            log.info("Aún esperando reCAPTCHA / botón Buscar…")
            last_log = now
        time.sleep(0.5)
    raise TimeoutException(
        f"«Buscar» no se habilitó en {timeout_s} s. Completa el reCAPTCHA en el navegador."
    )


def _stdin_readline_if_ready() -> bool:
    """
    Si hay una línea ya escrita en stdin (p. ej. Enter), la consume.

    Importante: **no** usar un hilo con readline() en paralelo a ``input()``:
    bloquea o roba stdin y entonces ``prompt_year()`` no recibe el año.
    En macOS/Linux usamos select; en Windows no hay poke por consola aquí.
    """
    if sys.platform == "win32":
        return False
    if not sys.stdin.isatty():
        return False
    try:
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r:
            return False
        sys.stdin.readline()
        return True
    except (ValueError, TypeError, OSError):
        return False


def interactive_captcha_wait(
    driver: webdriver.Chrome,
    *,
    is_ready,
    timeout_s: int,
    banner: str,
) -> None:
    """
    Espera a que ``is_ready(driver)`` sea True (p. ej. reCAPTCHA resuelto).

    Hasta ``timeout_s`` segundos. En macOS/Linux, si pulsas Enter en la misma
    consola, se fuerza un ciclo de comprobación (sin hilos que compitan con
    ``input()`` del año).
    """
    print(f"\n{banner}\n", file=sys.stderr)
    print(
        f"Tiempo máximo: {timeout_s} s (~{timeout_s // 60} min). "
        "El script sigue solo cuando la página esté lista.\n",
        file=sys.stderr,
    )
    if sys.platform != "win32" and sys.stdin.isatty():
        print(
            "(macOS/Linux: puedes pulsar Enter en esta terminal para forzar una comprobación.)\n",
            file=sys.stderr,
        )
    print(
        "(No está colgado: está comprobando el navegador.)\n",
        file=sys.stderr,
    )
    deadline = time.monotonic() + timeout_s
    last_log = 0.0
    while time.monotonic() < deadline:
        try:
            if is_ready(driver):
                log.info("Página lista para continuar.")
                return
        except StaleElementReferenceException:
            pass
        except Exception as e:
            log.debug("is_ready() falló (se reintenta): %s", e)
        if _stdin_readline_if_ready():
            log.info("Entrada en consola leída; comprobando de nuevo la página…")
        now = time.monotonic()
        if now - last_log >= 10:
            rem = deadline - now
            log.info("Aún esperando… ~%.0f s restantes en esta espera.", rem)
            print(
                f"  …esperando (~{rem:.0f} s restantes).\n",
                file=sys.stderr,
            )
            last_log = now
        time.sleep(0.4)
    raise TimeoutException(
        f"Tiempo agotado ({timeout_s} s) esperando que la página quede lista (reCAPTCHA / formulario)."
    )


def prompt_year() -> int | None:
    """Lee un año YYYY; cadena vacía → None (salir)."""
    while True:
        sys.stderr.write(
            "¿Qué año descargar? (YYYY). Enter vacío para terminar: "
        )
        sys.stderr.flush()
        raw = input().strip()
        if not raw:
            return None
        if raw.isdigit() and len(raw) == 4:
            y = int(raw)
            if 1900 <= y <= 2100:
                return y
        print("Introduce un año de 4 dígitos entre 1900 y 2100 (p. ej. 2023).", file=sys.stderr)


def prompt_yes_no(question: str) -> bool:
    raw = input(f"{question} [s/N]: ").strip().lower()
    return raw in ("s", "si", "sí", "y", "yes")


def click_buscar_estaciones(driver: webdriver.Chrome, timeout: int = 120) -> None:
    btn = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.ID, "filtroscirhform:buscar"))
    )
    btn.click()
    log.info("Pulsado «Buscar».")
    time.sleep(2.0)


def select_stations_by_matchers(
    driver: webdriver.Chrome,
    matchers: list[Union[list[str], dict[str, Any]]],
    timeout: int = 120,
) -> None:
    """
    Marca filas en listadoEstaciones.

    Cada elemento de ``matchers`` puede ser:

    - Lista de cadenas: todas deben aparecer en el texto de la fila.
    - Dict con ``include`` (obligatorias), ``exclude`` (si aparece alguna, se
      descarta la fila) y ``require_any`` (opcional: al menos una debe aparecer).

    Usa ``fold_station_text`` (Ñ→N) para alinear textos del portal con los criterios.

    Tras marcar la primera estación, RichFaces suele refrescar el DOM: se vuelve
    a leer las filas en cada paso.
    """
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, "filtroscirhform:listadoEstaciones_body"))
    )
    WebDriverWait(driver, timeout).until(
        lambda d: len(
            d.find_element(By.ID, "filtroscirhform:listadoEstaciones_body").find_elements(
                By.CSS_SELECTOR, "input[type='checkbox']"
            )
        )
        > 0
    )

    def _fresh_rows() -> list:
        b = driver.find_element(By.ID, "filtroscirhform:listadoEstaciones_body")
        return b.find_elements(By.XPATH, ".//tr")

    for pick in matchers:
        spec = _normalize_station_pick(pick)
        found = False
        wait_richfaces_idle(driver, timeout)
        time.sleep(0.4)
        rows = _fresh_rows()
        if not rows:
            raise FormAutomationError("Listado de estaciones sin filas.")

        for row in rows:
            try:
                rt = row.text
            except StaleElementReferenceException:
                log.debug("Fila obsoleta al leer texto; prueba siguiente fila.")
                continue
            if not _row_matches_station_spec(rt, spec):
                continue
            try:
                _click_station_checkbox(driver, row)
            except (NoSuchElementException, StaleElementReferenceException):
                continue
            log.info(
                "Estación seleccionada (%s): %s",
                spec,
                rt.replace("\n", " ")[:100],
            )
            found = True
            wait_richfaces_idle(driver, timeout)
            break
        if not found:
            # Ayuda al depurar: volver a leer textos tras posible AJAX.
            sample = []
            for r in _fresh_rows()[:12]:
                try:
                    sample.append(r.text.replace("\n", " ")[:100])
                except StaleElementReferenceException:
                    sample.append("(fila obsoleta)")
            log.error("Filas visibles en listado (muestra): %s", sample)
            raise FormAutomationError(
                f"No se encontró fila de estación para criterios {spec!r}. "
                f"Prueba -v y revisa el listado en el navegador."
            )


def apply_form_preset(
    driver: webdriver.Chrome,
    *,
    region_value: str,
    cuenca_partial: str,
    station_matchers: list[Union[list[str], dict[str, Any]]],
    meteo_title: str = "Reportes Meteorológicos",
    precip_label: str = "Precipitaciones Diarias",
) -> None:
    """Tras cargar /BNAConsultas/reportes: tipo informe, región, cuenca (sin reCAPTCHA ni Buscar)."""
    log.info("Configurando formulario (meteorológico / precipitación / región / cuenca)…")
    WebDriverWait(driver, 90).until(
        EC.presence_of_element_located((By.ID, "filtroscirhform:region"))
    )
    click_accordion_header(driver, meteo_title)
    time.sleep(1.0)
    check_report_checkbox_by_label(driver, precip_label)
    wait_richfaces_idle(driver, 120)
    time.sleep(0.5)
    ensure_busqueda_cuenca_o_nombre(driver)
    wait_richfaces_idle(driver, 120)
    select_region(driver, region_value)
    select_cuenca_by_partial_text(driver, cuenca_partial)
    log.info(
        "Formulario listo. Falta reCAPTCHA y «Buscar» para cargar el listado de estaciones."
    )


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    if verbose:
        # Evita inundar la consola con peticiones HTTP de bajo nivel.
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def scan_download_folder(download_dir: str) -> dict[str, tuple[float, int]]:
    """Nombre de archivo -> (mtime, size). Solo archivos directos (no subcarpetas)."""
    out: dict[str, tuple[float, int]] = {}
    if not os.path.isdir(download_dir):
        return out
    for name in os.listdir(download_dir):
        path = os.path.join(download_dir, name)
        if os.path.isfile(path):
            st = os.stat(path)
            out[name] = (st.st_mtime, st.st_size)
    return out


def log_download_changes(
    before: dict[str, tuple[float, int]],
    after: dict[str, tuple[float, int]],
    download_dir: str,
) -> None:
    """Describe archivos nuevos o que crecieron / actualizaron (típico de una descarga)."""
    new = []
    updated = []
    for name, (t2, s2) in after.items():
        if name not in before:
            new.append((name, s2))
        else:
            t1, s1 = before[name]
            if t2 > t1 or s2 != s1:
                updated.append((name, s1, s2))

    if new:
        for name, size in sorted(new):
            log.info(
                "Descarga detectada: archivo nuevo %r (%d bytes) en %s",
                name,
                size,
                download_dir,
            )
    if updated:
        for name, s1, s2 in sorted(updated):
            log.info(
                "Descarga detectada: archivo actualizado %r (%d -> %d bytes)",
                name,
                s1,
                s2,
            )
    if not new and not updated:
        log.warning(
            "No se detectó ningún archivo nuevo ni cambio de tamaño en %s tras la espera. "
            "Si el Excel debería haberse bajado, sube --wait-after-download o revisa el navegador.",
            download_dir,
        )

    partial = [n for n in after if n.endswith(".crdownload")]
    if partial:
        log.warning(
            "Aún hay descarga(s) en curso (.crdownload): %s — el archivo puede seguir bajándose.",
            ", ".join(sorted(partial)),
        )


def _folder_has_active_crdownload(snap: dict[str, tuple[float, int]]) -> bool:
    return any(n.endswith(".crdownload") for n in snap)


def _download_appears_complete(
    before: dict[str, tuple[float, int]], now: dict[str, tuple[float, int]]
) -> bool:
    """Hay archivo nuevo o creció, y no queda .crdownload (Chrome terminó el fichero)."""
    if _folder_has_active_crdownload(now):
        return False
    for name, (t2, s2) in now.items():
        if name.endswith(".crdownload"):
            continue
        if name not in before:
            return True
        t1, s1 = before[name]
        if s2 > s1 or t2 > t1:
            return True
    return False


def wait_for_download_or_enter(
    before: dict[str, tuple[float, int]],
    download_dir: str,
    max_wait_s: int,
) -> None:
    """
    Espera a que aparezca un fichero terminado en ``download_dir``, o a que el usuario
    pulse Enter (macOS/Linux vía select), o hasta ``max_wait_s``.
    """
    print(
        "\n>>> Cuando el Excel esté en la carpeta de descargas (o en la barra de Chrome), "
        "pulsa Enter aquí para continuar sin esperar el tiempo máximo.\n"
        f"    Carpeta: {os.path.abspath(download_dir)}\n"
        f"    Espera automática máx.: {max_wait_s} s (también se detecta archivo nuevo).\n",
        file=sys.stderr,
    )
    if sys.platform == "win32" or not sys.stdin.isatty():
        print(
            "(Enter anticipado solo en terminal macOS/Linux interactiva; aquí se usa tiempo máximo y/o detección de archivos.)\n",
            file=sys.stderr,
        )
    deadline = time.monotonic() + max_wait_s
    last_msg = 0.0
    while time.monotonic() < deadline:
        now = scan_download_folder(download_dir)
        if _download_appears_complete(before, now):
            log.info("Descarga completada detectada en la carpeta; continuando.")
            return
        if _stdin_readline_if_ready():
            log.info("Enter en consola: continúo (comprueba que el Excel haya terminado).")
            return
        t = time.monotonic()
        if t - last_msg >= 8:
            rem = deadline - t
            print(
                f"  …esperando descarga (~{rem:.0f} s máx.). Pulsa Enter si ya está listo.\n",
                file=sys.stderr,
            )
            last_msg = t
        time.sleep(0.35)
    log.info("Tiempo máximo de espera de descarga agotado; continuando.")


def parse_fecha(s: str) -> dt.datetime:
    """Acepta dd/mm/yyyy, dd-MM-yyyy o yyyy-mm-dd."""
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Fecha inválida: {s!r}. Use dd/mm/yyyy, dd-MM-yyyy o yyyy-mm-dd."
    )


def parse_download_dir(path: str) -> str:
    """Ruta absoluta para --download-dir; admite ``~/...``."""
    return os.path.abspath(os.path.expanduser(path.strip()))


_DEFAULT_DOWNLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "snia_downloads")
)


def iter_four_year_chunks(
    fecha_inicial: dt.datetime, fecha_final: dt.datetime
) -> list[tuple[dt.datetime, dt.datetime]]:
    """
    Bloques alineados al esquema de 4 años del script original (año N..N+3),
    recortados al rango pedido.
    """
    if fecha_final < fecha_inicial:
        raise ValueError("La fecha final debe ser >= fecha inicial.")

    chunks: list[tuple[dt.datetime, dt.datetime]] = []
    start_year = fecha_inicial.year
    end_year = fecha_final.year

    for y in range(start_year, end_year + 1, 4):
        chunk_start = dt.datetime(y, 1, 1)
        chunk_end = dt.datetime(y + 3, 12, 31, 23, 59, 59)
        actual_start = max(chunk_start, fecha_inicial)
        actual_end = min(chunk_end, fecha_final)
        if actual_start.date() <= actual_end.date():
            chunks.append((actual_start, actual_end))

    return chunks


def chunks_single_calendar_year(year: int) -> list[tuple[dt.datetime, dt.datetime]]:
    """
    Un solo tramo para todo el año civil: 01/01/year → 31/12/year
    (lo que se envía al portal como dd/mm/yyyy).
    """
    start = dt.datetime(year, 1, 1, 0, 0, 0, 0)
    end = dt.datetime(year, 12, 31, 23, 59, 59, 0)
    return [(start, end)]


def build_driver(download_dir: str) -> webdriver.Chrome:
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    opts = Options()
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    opts.add_experimental_option("prefs", prefs)

    log.info("Iniciando Chrome; descargas forzadas a: %s", download_dir)
    log.debug("Preferencias de descarga Chrome: %s", prefs)

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(180)
    log.debug(
        "Chrome iniciado (capabilities resumidas): browserName=%s",
        driver.capabilities.get("browserName"),
    )
    return driver


_POPUP_CLOSE_XPATH = '//*[@id="popupInfoMessage_header_controls"]/a'


def _extract_snia_popup_text(driver: webdriver.Chrome) -> str:
    """
    Lee el texto del modal RichFaces ``popupInfoMessage`` (p. ej. «no hay datos»).
    El DOM exacto varía; se prueban varios contenedores típicos.
    """
    candidates: list[tuple[Any, str]] = [
        (By.ID, "popupInfoMessage_content"),
        (By.CSS_SELECTOR, "#popupInfoMessage .rich-mpnl-body"),
        (By.CSS_SELECTOR, "#popupInfoMessage .rich-mpnl-content"),
        (
            By.XPATH,
            "//*[contains(@id,'popupInfoMessage') and contains(@id,'content')]",
        ),
        (By.XPATH, "//*[@id='popupInfoMessage']//td"),
    ]
    for by, sel in candidates:
        try:
            for node in driver.find_elements(by, sel):
                try:
                    if not node.is_displayed():
                        continue
                    t = (node.text or "").strip()
                    if len(t) >= 3:
                        return t
                except StaleElementReferenceException:
                    continue
        except Exception:
            continue
    try:
        root = driver.find_element(By.ID, "popupInfoMessage")
        if root.is_displayed():
            t = (root.text or "").strip()
            if t:
                return t
    except (NoSuchElementException, StaleElementReferenceException):
        pass
    return ""


def close_info_popup_if_any(driver: webdriver.Chrome, wait_s: float = 4.0) -> tuple[bool, str]:
    """
    Si aparece el diálogo (p. ej. sin datos), extrae el mensaje, lo escribe en
    consola (stderr) y log, cierra el popup y devuelve ``(True, mensaje)``.

    Si no aparece popup en ``wait_s`` s, devuelve ``(False, "")``.

    Tras «Generar XLS» el portal suele repintar el DOM: un WebElement guardado
    pasa a ser *stale* y ``is_displayed()`` falla en el segundo año. Por eso
    se vuelve a localizar el enlace en cada intento.
    """
    log.debug(
        "Buscando popup informativo (#popupInfoMessage) hasta %.1f s…", wait_s
    )
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        for el in driver.find_elements(By.XPATH, _POPUP_CLOSE_XPATH):
            try:
                if el.is_displayed():
                    msg = _extract_snia_popup_text(driver)
                    log.info(
                        "Portal mostró un mensaje emergente (p. ej. sin datos); "
                        "texto: %s",
                        repr(msg) if msg else "(no extraído)",
                    )
                    sep = "=" * 60
                    body = msg if msg else "(El portal mostró un aviso; no se pudo leer el texto.)"
                    print(
                        f"\n{sep}\nSNIA — aviso del portal:\n{body}\n{sep}\n",
                        file=sys.stderr,
                    )
                    time.sleep(0.5)
                    try:
                        el.click()
                    except (StaleElementReferenceException, ElementClickInterceptedException):
                        driver.execute_script(
                            "var x=arguments[0];"
                            "var n=document.evaluate(x,document,null,"
                            "XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;"
                            "if(n) n.click();",
                            _POPUP_CLOSE_XPATH,
                        )
                    time.sleep(1.5)
                    return True, msg
            except StaleElementReferenceException:
                continue
        time.sleep(0.25)
    log.debug("No apareció popup informativo usable en %.1f s (sigue flujo de descarga).", wait_s)
    return False, ""


def _set_snia_date_input(driver: webdriver.Chrome, el, date_dd_mm_yyyy: str) -> None:
    """
    Rellena un input de fecha JSF/RichFaces. clear()+send_keys a veces deja mal el año;
    usamos seleccionar todo + teclado + refuerzo con value y eventos.
    """
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    el.click()
    time.sleep(0.12)
    mod = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
    el.send_keys(mod, "a")
    el.send_keys(Keys.BACKSPACE)
    el.send_keys(date_dd_mm_yyyy)
    driver.execute_script(
        """
        var e = arguments[0], v = arguments[1];
        if (e) {
          e.value = v;
          e.dispatchEvent(new Event('input', { bubbles: true }));
          e.dispatchEvent(new Event('change', { bubbles: true }));
          e.dispatchEvent(new Event('blur', { bubbles: true }));
        }
        """,
        el,
        date_dd_mm_yyyy,
    )


def _clear_snia_date_fields(driver: webdriver.Chrome) -> None:
    """
    Limpia desde/hasta. Tras «Generar XLS» o cerrar el popup, RichFaces repinta
    el formulario: hay que volver a localizar los inputs (referencias antiguas = stale).
    """
    for name in (
        "filtroscirhform:fechaDesdeInputDate",
        "filtroscirhform:fechaHastaInputDate",
    ):
        for _attempt in range(10):
            try:
                el = driver.find_element(By.NAME, name)
                el.clear()
                driver.execute_script(
                    "var e=arguments[0]; if(e){ e.value='';"
                    "e.dispatchEvent(new Event('input',{bubbles:true}));"
                    "e.dispatchEvent(new Event('change',{bubbles:true}));"
                    "e.dispatchEvent(new Event('blur',{bubbles:true})); }",
                    el,
                )
                break
            except StaleElementReferenceException:
                time.sleep(0.25)
        else:
            log.warning("No se pudo limpiar el campo %s (sigue stale).", name)
    log.debug("Campos de fecha limpiados para el siguiente tramo.")


def set_dates_and_download(
    driver: webdriver.Chrome,
    desde: dt.datetime,
    hasta: dt.datetime,
    post_download_sleep_s: int = 30,
    download_dir: str | None = None,
) -> None:
    fmt = "%d/%m/%Y"
    desde_s = desde.strftime(fmt)
    hasta_s = hasta.strftime(fmt)

    log.info("Rellenando fechas en el formulario: desde=%s hasta=%s (formato portal dd/mm/yyyy)", desde_s, hasta_s)
    log.debug("URL actual: %s", driver.current_url)

    t0 = time.perf_counter()
    fecha_desde = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.NAME, "filtroscirhform:fechaDesdeInputDate"))
    )
    log.debug("Campo fechaDesde localizado en %.2f s", time.perf_counter() - t0)

    fecha_hasta = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.NAME, "filtroscirhform:fechaHastaInputDate"))
    )
    _set_snia_date_input(driver, fecha_desde, desde_s)
    _set_snia_date_input(driver, fecha_hasta, hasta_s)
    try:
        vd = fecha_desde.get_attribute("value")
        vh = fecha_hasta.get_attribute("value")
        log.info("Valores en campos fecha (atributo value): %r / %r", vd, vh)
    except StaleElementReferenceException:
        pass
    log.debug("Fechas aplicadas (teclado + JS).")

    before = scan_download_folder(download_dir) if download_dir else {}

    descargar_xl = WebDriverWait(driver, 120).until(
        EC.element_to_be_clickable((By.NAME, "filtroscirhform:generarxls"))
    )
    log.info('Pulsando «Generar XLS» (name=filtroscirhform:generarxls)…')
    descargar_xl.click()

    had_popup, _popup_msg = close_info_popup_if_any(driver)
    if had_popup:
        log.info(
            "Este tramo no generó descarga (el portal mostró un aviso); fechas limpiadas. "
            "En modo interactivo por año, al terminar podrás elegir otro año si quieres."
        )
        print(
            "\n(No hubo archivo Excel para este tramo. Si usas el modo por años, "
            "al cerrar este año se te preguntará si quieres descargar otro.)\n",
            file=sys.stderr,
        )
        _clear_snia_date_fields(driver)
        return

    if download_dir:
        wait_for_download_or_enter(before, download_dir, post_download_sleep_s)
    else:
        log.info(
            "Sin carpeta de descargas conocida: esperando %d s fijos…",
            post_download_sleep_s,
        )
        time.sleep(post_download_sleep_s)

    if download_dir:
        after = scan_download_folder(download_dir)
        log.debug(
            "Archivos en carpeta de descarga tras la espera: %d entradas",
            len(after),
        )
        log_download_changes(before, after, download_dir)

    _clear_snia_date_fields(driver)


def run_download_chunks(
    driver: webdriver.Chrome,
    chunks: list[tuple[dt.datetime, dt.datetime]],
    download_abs: str,
    wait_after_download: int,
) -> None:
    n = len(chunks)
    for i, (desde, hasta) in enumerate(chunks, start=1):
        log.info(
            "=== Tramo %d/%d: %s → %s ===",
            i,
            n,
            desde.date(),
            hasta.date(),
        )
        set_dates_and_download(
            driver,
            desde,
            hasta,
            post_download_sleep_s=wait_after_download,
            download_dir=download_abs,
        )


def main() -> int:
    default_end = dt.datetime.now()
    default_start = dt.datetime(2020, 1, 1)

    p = argparse.ArgumentParser(
        description="Descarga reportes SNIA vía navegador + Selenium (fechas y, opcionalmente, formulario)."
    )
    p.add_argument(
        "--fecha-inicio",
        type=parse_fecha,
        default=default_start,
        help="Inicio (dd/mm/yyyy, dd-MM-yyyy o yyyy-mm-dd). Por defecto: 2020-01-01.",
    )
    p.add_argument(
        "--fecha-fin",
        type=parse_fecha,
        default=default_end,
        help="Fin del periodo. Por defecto: hoy.",
    )
    p.add_argument(
        "-d",
        "--download-dir",
        type=parse_download_dir,
        default=_DEFAULT_DOWNLOAD_DIR,
        metavar="DIR",
        help=(
            "Carpeta donde Chrome guardará los Excel (se crea al iniciar el navegador si no existe). "
            "Rutas relativas, absolutas o con ~/ — ej. -d ~/Downloads/snia_mop"
        ),
    )
    p.add_argument(
        "--wait-after-download",
        type=int,
        default=120,
        help=(
            "Tiempo máximo de espera tras «Generar XLS» (por defecto 120 s). "
            "El script detecta archivos nuevos en la carpeta y, en macOS/Linux, "
            "puedes pulsar Enter en consola en cuanto veas la descarga lista."
        ),
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Salida DEBUG (pasos Selenium, URL, detalle de carpeta de descargas).",
    )
    p.add_argument(
        "--preset",
        choices=sorted(FORM_PRESETS.keys()),
        default=None,
        help=(
            "Rellena el formulario antes del reCAPTCHA. "
            "rinihue-precip-valdivia: Reportes Meteorológicos → Precipitaciones Diarias, "
            "Los Ríos, cuenca Río Valdivia, y marca Lago Riñihue (Meteo) + estación de control."
        ),
    )
    p.add_argument(
        "--region-value",
        default=None,
        help=(
            "Con --preset: región. Usa el value del <option> (recomendado: 14 para DE LOS RIOS), "
            "o el texto visible / «Los Ríos»; no confundir: el value no es la cadena «DE LOS RIOS»."
        ),
    )
    p.add_argument(
        "--cuenca-partial",
        default=None,
        help="Con --preset: texto parcial para elegir la cuenca en el segundo desplegable.",
    )
    p.add_argument(
        "--captcha-wait-s",
        type=int,
        default=600,
        help="Segundos máximos esperando «Buscar» tras reCAPTCHA (modo no interactivo con --preset).",
    )
    p.add_argument(
        "--no-interactive-years",
        action="store_true",
        help=(
            "No preguntar el año por consola: usar --fecha-inicio y --fecha-fin "
            "(tramos automáticos de hasta 4 años)."
        ),
    )
    p.add_argument(
        "--interactive-captcha-wait-s",
        type=int,
        default=300,
        help=(
            "Segundos máximos en cada espera interactiva de reCAPTCHA (5 min por defecto). "
            "Puedes pulsar Enter en consola cuando lo hayas pasado para comprobar al instante."
        ),
    )
    args = p.parse_args()

    setup_logging(args.verbose)
    log.debug("Argumentos: %s", args)

    interactive_years = not args.no_interactive_years
    if interactive_years:
        log.info(
            "Modo interactivo por año: se pedirá el año en consola (01/01–31/12). "
            "Para un rango fijo usa --no-interactive-years con --fecha-inicio/--fecha-fin."
        )

    download_abs = os.path.abspath(args.download_dir)
    log.info("Carpeta de descargas: %s", download_abs)

    driver = build_driver(args.download_dir)
    try:
        log.info("Abriendo %s", SNIA_REPORTES_URL)
        driver.get(SNIA_REPORTES_URL)
        log.debug("Título de la página: %s", driver.title)

        if args.preset:
            cfg = dict(FORM_PRESETS[args.preset])
            if args.region_value is not None:
                cfg["region_value"] = args.region_value
            if args.cuenca_partial is not None:
                cfg["cuenca_partial"] = args.cuenca_partial
            try:
                apply_form_preset(
                    driver,
                    region_value=str(cfg["region_value"]),
                    cuenca_partial=str(cfg["cuenca_partial"]),
                    station_matchers=list(cfg["station_matchers"]),
                )
            except FormAutomationError as e:
                log.error("%s", e)
                return 2

            print(
                "\nEl script ya aplicó el tipo de informe, región y cuenca del preset.\n",
                file=sys.stderr,
            )
            try:
                if interactive_years:
                    interactive_captcha_wait(
                        driver,
                        is_ready=_buscar_is_enabled,
                        timeout_s=args.interactive_captcha_wait_s,
                        banner=(
                            ">>> reCAPTCHA: resuélvelo en el navegador para habilitar «Buscar»."
                        ),
                    )
                else:
                    print(
                        "  → Completa el reCAPTCHA. Cuando «Buscar» esté activo, el script seguirá solo.\n",
                        file=sys.stderr,
                    )
                    wait_for_buscar_enabled(driver, timeout_s=args.captcha_wait_s)
                click_buscar_estaciones(driver)
                select_stations_by_matchers(
                    driver, list(cfg["station_matchers"]), timeout=120
                )
            except (TimeoutException, FormAutomationError, ValueError) as e:
                log.error("%s", e)
                return 2
        else:
            print(
                "\nEn el navegador:\n"
                "  1) Completa el reCAPTCHA.\n"
                "  2) Elige el informe que corresponda.\n"
                "  3) Busca y selecciona la(s) estación(es).\n"
                "  4) Deja la pantalla lista para usar «Generar XLS».\n"
                "\n(O usa --preset rinihue-precip-valdivia para automatizar parte del formulario.)\n",
                file=sys.stderr,
            )
            if interactive_years:
                interactive_captcha_wait(
                    driver,
                    is_ready=_generar_xls_is_ready,
                    timeout_s=args.interactive_captcha_wait_s,
                    banner=(
                        ">>> Cuando el formulario esté listo (reCAPTCHA hecho y estaciones elegidas), "
                        "el script detectará «Generar XLS» habilitado."
                    ),
                )
            else:
                input("Cuando esté listo, pulsa Enter aquí para comenzar las descargas… ")

        if interactive_years:
            while True:
                year = prompt_year()
                if year is None:
                    log.info("Fin de descargas por año (entrada vacía).")
                    break
                interactive_captcha_wait(
                    driver,
                    is_ready=_generar_xls_is_ready,
                    timeout_s=args.interactive_captcha_wait_s,
                    banner=(
                        f">>> Antes de descargar {year}: si aparece reCAPTCHA u otra pantalla de bloqueo, "
                        "resuélvela en el navegador."
                    ),
                )
                chunks = chunks_single_calendar_year(year)
                print(
                    f"\nAño {year}: fecha inicial 01/01/{year}, fecha final 31/12/{year} "
                    f"(formato del portal: dd/mm/yyyy).\n",
                    file=sys.stderr,
                )
                log.info(
                    "Descarga año calendario %s: desde 01/01/%s hasta 31/12/%s (un solo tramo).",
                    year,
                    year,
                    year,
                )
                desde, hasta = chunks[0]
                log.info(
                    "  Tramo único: %s → %s",
                    desde.strftime("%d/%m/%Y"),
                    hasta.strftime("%d/%m/%Y"),
                )
                run_download_chunks(
                    driver,
                    chunks,
                    download_abs,
                    args.wait_after_download,
                )
                if not prompt_yes_no("¿Quieres descargar otro año?"):
                    break
        else:
            fecha_inicial = args.fecha_inicio.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            fecha_final = args.fecha_fin.replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            chunks = iter_four_year_chunks(fecha_inicial, fecha_final)
            if not chunks:
                log.error("No hay tramos de fechas que descargar.")
                return 1
            log.info(
                "Rango solicitado: %s → %s (%d tramo(s) de hasta 4 años):",
                fecha_inicial.date(),
                fecha_final.date(),
                len(chunks),
            )
            for a, b in chunks:
                log.info("  Tramo: %s → %s", a.strftime("%d/%m/%Y"), b.strftime("%d/%m/%Y"))
            run_download_chunks(
                driver,
                chunks,
                download_abs,
                args.wait_after_download,
            )

        log.info("Ciclo de descargas terminado. Revisa: %s", download_abs)
    finally:
        log.debug("Cerrando navegador…")
        driver.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
