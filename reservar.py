#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de reservas CORE (corefit.misactividades.com)

Reserva automaticamente la clase de las 08:00 (o la primera clase del dia si ese
dia no hay 8am) para el dia +7, disparando a las 00:01 hora de Argentina.

Uso:
    python reservar.py            # modo real (reserva de verdad)
    python reservar.py --dry-run  # hace TODO menos el click final "Reservar"
    python reservar.py --now      # no espera hasta las 00:01, ejecuta ya

Configuracion por variables de entorno (ver .env.example):
    COREFIT_EMAIL      (obligatoria)  email de login
    COREFIT_PASSWORD   (obligatoria)  contrasena de login
    COREFIT_TARGET_TIME  (def 08:00)  horario objetivo
    COREFIT_DAYS_AHEAD   (def 7)      cuantos dias hacia adelante reservar
    COREFIT_FIRE_TIME    (def 00:01)  hora local a la que dispara la reserva
    COREFIT_TZ           (def America/Argentina/Buenos_Aires)
    COREFIT_BRANCH       (def vacio)  nombre de sucursal (vacio = la que viene por defecto)
    COREFIT_HEADLESS     (def true)   correr sin ventana
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE_URL = "https://corefit.misactividades.com"
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")


# --------------------------------------------------------------------------- #
# Config y logging
# --------------------------------------------------------------------------- #
def _load_dotenv():
    """Carga un archivo .env (si existe) sin dependencias externas.
    En GitHub Actions no hay .env: se usan Secrets, así que esto no molesta."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def load_config():
    _load_dotenv()
    tz = ZoneInfo(os.environ.get("COREFIT_TZ", "America/Argentina/Buenos_Aires"))
    return {
        "email": os.environ.get("COREFIT_EMAIL", "").strip(),
        "password": os.environ.get("COREFIT_PASSWORD", ""),
        "target_time": os.environ.get("COREFIT_TARGET_TIME", "08:00").strip(),
        "days_ahead": int(os.environ.get("COREFIT_DAYS_AHEAD", "7")),
        "fire_time": os.environ.get("COREFIT_FIRE_TIME", "00:01").strip(),
        "branch": os.environ.get("COREFIT_BRANCH", "").strip(),
        "headless": os.environ.get("COREFIT_HEADLESS", "true").lower() != "false",
        "tz": tz,
    }


def log(msg):
    tz = ZoneInfo(os.environ.get("COREFIT_TZ", "America/Argentina/Buenos_Aires"))
    ts = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def shot(page, name):
    """Guarda un screenshot para debug (se suben como artifact en GitHub Actions)."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{ts}_{name}.png")
        page.screenshot(path=path, full_page=True)
        log(f"  screenshot -> {path}")
    except Exception as e:
        log(f"  (no se pudo guardar screenshot: {e})")


# --------------------------------------------------------------------------- #
# Timing: esperar hasta las 00:01 AR
# --------------------------------------------------------------------------- #
def compute_fire_datetime(now, fire_time):
    """Devuelve el datetime (tz-aware) del proximo disparo.

    Si estamos a la tarde/noche (hora >= 12), el disparo es la medianoche que
    viene (dia siguiente) a las fire_time. Si ya estamos pasada la medianoche,
    es hoy a las fire_time (y si ya paso, se dispara de inmediato)."""
    hh, mm = (int(x) for x in fire_time.split(":"))
    if now.hour >= 12:
        base = now + timedelta(days=1)
    else:
        base = now
    return base.replace(hour=hh, minute=mm, second=0, microsecond=0)


def wait_until(target_dt, tz, max_minutes=30):
    """Espera (bloqueante) hasta target_dt, con tope de seguridad."""
    now = datetime.now(tz)
    if now >= target_dt:
        log(f"Ya pasó la hora de disparo ({target_dt:%H:%M:%S}); ejecuto de inmediato.")
        return
    delta = (target_dt - now).total_seconds()
    if delta > max_minutes * 60:
        log(f"AVISO: faltan {delta/60:.1f} min hasta el disparo (más que el tope de "
            f"{max_minutes} min). Limito la espera al tope.")
        delta = max_minutes * 60
    log(f"Esperando hasta las {target_dt:%H:%M:%S} ({delta:.0f}s)...")
    # Espera en tramos para ir logueando la cuenta regresiva.
    end = time.monotonic() + delta
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        # Ultimos 10s: precision fina
        if remaining <= 10:
            time.sleep(min(remaining, 0.2))
        elif remaining <= 60:
            time.sleep(1)
        else:
            time.sleep(min(remaining - 55, 15))
    log(f"¡Hora de disparo! ({datetime.now(tz):%H:%M:%S})")


# --------------------------------------------------------------------------- #
# Pasos del flujo en la web
# --------------------------------------------------------------------------- #
def is_login_form_visible(page):
    return page.query_selector("#email") is not None


def is_logged_in(page):
    body = (page.inner_text("body") or "").lower()
    return ("gestiona tus reservas" in body) or ("salir" in body and "tu perfil" in body)


def login(page, email, password):
    log("Login: abriendo formulario...")
    page.goto(f"{BASE_URL}/#login", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#email", timeout=8000)
    except PWTimeout:
        # Fallback: home -> "Tengo usuario"
        page.goto(f"{BASE_URL}/#home", wait_until="domcontentloaded")
        page.click("text=Tengo usuario", timeout=8000)
        page.wait_for_selector("#email", timeout=10000)

    page.fill("#email", email)
    page.fill("#password", password)
    log("Login: enviando credenciales...")
    page.get_by_role("link", name="Ingresar", exact=True).click()

    # Esperar dashboard o detectar error
    try:
        page.wait_for_function(
            """() => {
                const b = (document.body.innerText || '').toLowerCase();
                return b.includes('gestiona tus reservas') ||
                       (b.includes('salir') && b.includes('tu perfil'));
            }""",
            timeout=20000,
        )
    except PWTimeout:
        body = (page.inner_text("body") or "").lower()
        if "email" in body and ("incorrect" in body or "inv" in body or "no coincide" in body
                                or "erron" in body or "contraseña" in body):
            raise RuntimeError("Login falló: revisar email/contraseña (¿credenciales inválidas?).")
        raise RuntimeError("Login: no se detectó el panel tras iniciar sesión.")
    log("Login OK.")


def go_to_bookings(page):
    log("Navegando a Reservas...")
    # Intento por click en la tarjeta del dashboard; si no, por hash.
    try:
        page.click("text=Gestiona tus reservas de clases", timeout=5000)
    except PWTimeout:
        page.goto(f"{BASE_URL}/#bookings", wait_until="domcontentloaded")
    # Hay muchos .date-selector-item ocultos en el DOM; esperamos uno VISIBLE.
    page.wait_for_selector(".date-selector-item:visible", timeout=15000)
    log("En pantalla de Reservas.")


def ensure_bookings(page, email, password):
    """Garantiza estar en la pantalla de reservas, re-logueando si hizo falta."""
    for _ in range(2):
        if is_login_form_visible(page):
            login(page, email, password)
        try:
            go_to_bookings(page)
            return True
        except PWTimeout:
            # Puede que un reload nos haya dejado en otra vista; reintento.
            page.goto(f"{BASE_URL}/#home", wait_until="domcontentloaded")
    return False


def select_branch(page, branch):
    """Selecciona la sucursal si se especificó una (por defecto se deja la que viene)."""
    if not branch:
        return
    try:
        sel = page.query_selector("select")
        if sel:
            page.select_option("select", label=branch)
            page.wait_for_timeout(1200)
            log(f"Sucursal seleccionada: {branch}")
    except Exception as e:
        log(f"AVISO: no pude fijar la sucursal '{branch}': {e}")


def select_date(page, date_str):
    # Apuntamos al chip VISIBLE de esa fecha (hay copias ocultas en el DOM).
    loc = page.locator(f'.date-selector-item[data-date="{date_str}"]:visible').first
    try:
        loc.wait_for(state="visible", timeout=10000)
    except PWTimeout:
        return False
    loc.click()
    # Esperar a que carguen las clases del día (AJAX) + margen.
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PWTimeout:
        pass
    page.wait_for_timeout(800)
    return True


def get_classes(page):
    """Lista de clases visibles: [{id, time, full, reserved, text}], ordenada por hora."""
    classes = page.evaluate(
        r"""() => {
        // Solo filas de clase reales: id = "booking-<GUID>" (no el contenedor "booking-by-date-list").
        const rows = [...document.querySelectorAll('[id^="booking-"]')]
            .filter(r => /^booking-[0-9a-f]{8}-[0-9a-f]{4}-/i.test(r.id));
        return rows.map(r => {
            const txt = (r.innerText || '').replace(/\s+/g, ' ').trim();
            const m = txt.match(/\b(\d{2}:\d{2})\b/);
            const box = r.querySelector('[class*="border-box"]') || r;
            const cls = ((box.className || '') + ' ' + (r.className || '')).toLowerCase();
            return {
                id: r.id,
                time: m ? m[1] : null,
                full: /cupo completo/i.test(txt),
                reserved: /green/.test(cls),
                text: txt.slice(0, 70),
            };
        }).filter(c => c.time);
    }"""
    )
    classes.sort(key=lambda c: c["time"])
    return classes


def pick_target_class(classes, target_time):
    """Regla: la clase de target_time; si ese dia no existe, la primera del dia."""
    exact = [c for c in classes if c["time"] == target_time]
    if exact:
        return exact[0], "objetivo"
    if classes:
        return classes[0], "primera-del-dia (no hay clase a las %s)" % target_time
    return None, "sin-clases"


def verify_reserved(page, email, password, date_str, target_time):
    """Vuelve a la lista del dia y confirma que la clase quedó en verde (reservada)."""
    try:
        page.goto(f"{BASE_URL}/#home", wait_until="domcontentloaded")
        ensure_bookings(page, email, password)
        if not select_date(page, date_str):
            return False
        classes = get_classes(page)
        for c in classes:
            if c["time"] == target_time:
                return c["reserved"]
    except Exception as e:
        log(f"AVISO: no pude verificar la reserva: {e}")
    return False


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(cfg, dry_run, fire_now):
    tz = cfg["tz"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg["headless"])
        context = browser.new_context(
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(20000)

        try:
            # 1) Login + calentar sesión antes de la medianoche.
            login(page, cfg["email"], cfg["password"])
            go_to_bookings(page)
            select_branch(page, cfg["branch"])
            shot(page, "01_prelogin_bookings")

            # 2) Esperar hasta las 00:01 AR (salvo --now).
            if not fire_now:
                fire = compute_fire_datetime(datetime.now(tz), cfg["fire_time"])
                wait_until(fire, tz)

            # 3) Recargar para que aparezca el nuevo día +7 (los cupos abren a las 00:00).
            log("Recargando para tomar el día recién abierto...")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            if not ensure_bookings(page, cfg["email"], cfg["password"]):
                raise RuntimeError("No pude volver a la pantalla de Reservas tras recargar.")
            select_branch(page, cfg["branch"])

            # 4) Calcular la fecha objetivo (hoy AR + N días) y seleccionarla.
            now = datetime.now(tz)
            target_date = (now + timedelta(days=cfg["days_ahead"])).strftime("%Y-%m-%d")
            log(f"Fecha objetivo: {target_date} (hoy {now:%Y-%m-%d} + {cfg['days_ahead']} días)")
            if not select_date(page, target_date):
                shot(page, "err_no_date")
                raise RuntimeError(f"No apareció el día {target_date} en el selector.")

            # 5) Elegir la clase.
            classes = get_classes(page)
            log(f"Clases del {target_date}: " +
                ", ".join(f"{c['time']}{'(lleno)' if c['full'] else ''}"
                          f"{'(reservada)' if c['reserved'] else ''}" for c in classes))
            chosen, reason = pick_target_class(classes, cfg["target_time"])
            if chosen is None:
                shot(page, "err_no_classes")
                raise RuntimeError(f"No hay clases listadas para {target_date}.")
            log(f"Clase elegida: {chosen['time']} [{reason}]  id={chosen['id']}")

            if chosen["reserved"]:
                log(f"La clase de las {chosen['time']} YA figura reservada. Nada que hacer. ✔")
                shot(page, "02_already_reserved")
                return 0

            # 6) Abrir el detalle de la clase.
            page.click(f'[id="{chosen["id"]}"]')
            page.wait_for_selector("#register", timeout=10000)
            detail = (page.inner_text("body") or "").lower()
            waitlist = "lista de espera" in detail
            if waitlist:
                log("AVISO: la clase figura llena; 'Reservar' entra en LISTA DE ESPERA.")
            shot(page, "03_detail")

            # 7) Tocar 'Reservar' -> aparece el modal "Condiciones de reserva".
            log("Tocando 'Reservar'...")
            page.click("#register")
            has_modal = True
            try:
                page.wait_for_selector("#modalBookingConditionsConfirm", state="visible",
                                       timeout=8000)
            except PWTimeout:
                has_modal = False
                log("AVISO: no apareció el modal de condiciones (¿reserva directa?).")
            shot(page, "04_modal_condiciones")

            # 8) Dry-run: cancelar el modal. Real: Aceptar (reserva de verdad).
            if dry_run:
                log("DRY-RUN: llegué a la confirmación 'Condiciones de reserva' pero NO acepto.")
                if has_modal:
                    try:
                        page.click("#modalBookingConditions .modal-close")
                    except Exception:
                        pass
                log("Flujo completo validado. ✔")
                return 0

            if has_modal:
                log("Aceptando condiciones de reserva...")
                page.click("#modalBookingConditionsConfirm")
                page.wait_for_timeout(2500)
            shot(page, "05_post_reservar")

            # 9) Verificar.
            ok = verify_reserved(page, cfg["email"], cfg["password"], target_date, chosen["time"])
            if ok:
                estado = "EN LISTA DE ESPERA" if waitlist else "CONFIRMADA"
                log(f"RESERVA {estado}: {target_date} {chosen['time']}. ✔")
                shot(page, "06_verificada")
                return 0
            else:
                log("No pude CONFIRMAR que la reserva quedó registrada. Revisar screenshots.")
                shot(page, "err_sin_confirmar")
                return 2

        except Exception as e:
            log(f"ERROR: {e}")
            try:
                shot(page, "error")
            except Exception:
                pass
            return 1
        finally:
            context.close()
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="Bot de reservas CORE")
    parser.add_argument("--dry-run", action="store_true",
                        help="Hace todo menos el click final de reservar.")
    parser.add_argument("--now", action="store_true",
                        help="No espera hasta las 00:01; ejecuta de inmediato.")
    args = parser.parse_args()

    # Salida UTF-8 (para que los emojis/✔ no rompan en la consola de Windows).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    cfg = load_config()
    if not cfg["email"] or not cfg["password"]:
        log("FALTAN credenciales: definí COREFIT_EMAIL y COREFIT_PASSWORD.")
        sys.exit(3)

    log("=== Bot de reservas CORE ===")
    log(f"Objetivo: {cfg['target_time']} | +{cfg['days_ahead']} días | "
        f"disparo {cfg['fire_time']} AR | dry_run={args.dry_run} | now={args.now}")
    code = run(cfg, dry_run=args.dry_run, fire_now=args.now)
    log(f"=== Fin (exit {code}) ===")
    sys.exit(code)


if __name__ == "__main__":
    main()
