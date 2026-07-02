# Bot de reservas CORE 🏋️

Reserva automáticamente tu clase en **corefit.misactividades.com** todos los días
de **lunes a viernes**, apenas se abren los cupos.

- Cada día a las **00:01 (hora Argentina)** reserva la clase de las **08:00** para
  el día **+7** (la semana siguiente).
- Si ese día no hay clase a las 08:00 (ej. los jueves, que arrancan 09:00), reserva
  **la primera clase del día**.
- Corre solo en **GitHub Actions** (no necesitás dejar la PC prendida).

---

## 🧠 Cómo funciona

1. Inicia sesión con tu usuario y contraseña.
2. Entra a **Reservas** y **espera hasta las 00:01 AR** para disparar.
3. Recarga, selecciona el día +7 (por el atributo `data-date`, súper confiable).
4. Busca la clase de las 08:00 (o la primera del día) y toca **Reservar**.
5. Verifica que la clase haya quedado reservada y guarda un screenshot.

### Sobre el horario ⏰
El cron de GitHub Actions **no es puntual** (puede atrasarse varios minutos, sobre
todo a la medianoche). Por eso el workflow arranca a las **23:50 AR** y el propio
bot **espera hasta las 00:01** para disparar. Así la hora la controla el bot y no
el cron.

---

## 🚀 Puesta en marcha (una sola vez)

1. **Creá un repo nuevo en GitHub** y subí estos archivos (ver más abajo).
2. Cargá tus credenciales como **Secrets** (NO van en el código):
   - Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   - Creá dos secrets:
     - `COREFIT_EMAIL` → tu email
     - `COREFIT_PASSWORD` → tu contraseña
3. (Opcional) En la misma pantalla, pestaña **Variables**, podés crear:
   - `COREFIT_TARGET_TIME` (ej. `08:00`)
   - `COREFIT_DAYS_AHEAD` (ej. `7`)
   - `COREFIT_FIRE_TIME` (ej. `00:01`)
   - `COREFIT_BRANCH` (ej. `BELGRANO, ARCOS` — vacío usa la sucursal por defecto)
4. Repo → pestaña **Actions** → habilitá los workflows si te lo pide.

¡Listo! De lunes a viernes va a correr solo.

---

## 🧪 Probarlo sin reservar de verdad

### En GitHub (recomendado)
Repo → **Actions** → **Reservar clase CORE** → **Run workflow**.
Dejá `dry_run = true` y `now = true`: hace **todo el flujo menos el click final**
de reservar. Después mirá el log y descargá el artifact **screenshots**.

### En tu PC
```bash
pip install -r requirements.txt
python -m playwright install chromium

# copiá .env.example a .env y completá tus datos, luego:
python reservar.py --dry-run --now     # prueba todo, sin reservar
python reservar.py --now               # reserva YA (para el día +7)
python reservar.py                     # espera hasta las 00:01 y reserva
```

---

## ⚙️ Flags y configuración

| Flag           | Qué hace                                             |
|----------------|------------------------------------------------------|
| `--dry-run`    | Llega al botón "Reservar" pero **no** lo toca.       |
| `--now`        | No espera hasta las 00:01; ejecuta de inmediato.     |

Variables de entorno: ver [`.env.example`](.env.example).

---

## ⚠️ Riesgos conocidos

1. **Puntualidad del cron de GitHub.** Mitigado con el arranque anticipado + espera
   interna, pero si GitHub se atrasa mucho, la reserva podría dispararse tarde.
2. **Bloqueo de IP.** La web podría rechazar las IP de datacenter de GitHub. Si en
   las pruebas ves errores de acceso/timeouts de login, la alternativa más confiable
   es correr el bot en **tu propia PC** con el **Programador de tareas de Windows**
   (IP residencial + hora exacta). El mismo `reservar.py` sirve para las dos cosas.

---

## 🔒 Seguridad

- La contraseña y el email **nunca** están en el código: van en **GitHub Secrets**.
- El archivo `.env` local está en `.gitignore` (no se sube).
- Si alguna vez compartiste la contraseña en texto plano, conviene **cambiarla**
  y actualizar el secret.

---

## 📁 Estructura

```
.
├── reservar.py                    # el bot
├── requirements.txt               # dependencias (playwright)
├── .env.example                   # plantilla de configuración local
├── .gitignore
└── .github/workflows/reservar.yml # el cron de GitHub Actions
```
