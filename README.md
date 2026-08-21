# Bot de reservas CORE 🏋️

Reserva automáticamente tu clase en **corefit.misactividades.com** todos los días
de **lunes a viernes**, apenas se abren los cupos.

- Cada día a las **08:00 (hora Argentina)** reserva la clase de las **08:00** para
  el día **+7** (la semana siguiente). La inscripción a cada clase se habilita a la
  **misma hora de la clase**, una semana antes.
- Si ese día no hay clase a las 08:00 (ej. los jueves, que arrancan 09:00), reserva
  **la primera clase del día**.
- Corre solo en **GitHub Actions** (no necesitás dejar la PC prendida).

---

## 🧠 Cómo funciona

1. Inicia sesión con tu usuario y contraseña.
2. Recarga y selecciona el día **+7** (por el atributo `data-date`, súper confiable).
3. Busca la clase de las 08:00 (o la primera del día) y toca **Reservar**.
4. Acepta el modal de **"Condiciones de reserva"**.
5. Verifica que la clase haya quedado reservada y guarda un screenshot.

### Sobre el horario ⏰
La inscripción a cada clase se habilita **a la misma hora de la clase, una semana
antes**: la de las 08:00 abre a las **08:00 AR** del mismo día de la semana previa.
Por eso el bot dispara a las **08:00**. El disparo puntual lo hace **cron-job.org**
(gratis), que a las **08:00 AR** de lunes a viernes dispara el workflow por API
(`workflow_dispatch`, que corre al instante). El cron interno de GitHub se atrasa
3-4,5 h, así que queda solo de **respaldo tardío** (reserva ~11:00-13:00 AR, útil
únicamente si el cupo sigue libre a esa hora). El bot es idempotente: si la clase
ya está reservada, no hace nada, así que pueden convivir varios disparos.

#### Configuración del disparador externo (cron-job.org)
1. **Token de GitHub** (una vez): GitHub → Settings → Developer settings →
   *Fine-grained personal access tokens* → Generate new token.
   - Repository access: **Only select repositories** → `core-bot`
   - Permissions → Repository permissions → **Actions: Read and write**
   - Expiración: la máxima que permita (anotar renovarlo).
2. **Cronjob** en [cron-job.org](https://console.cron-job.org) (cuenta gratis):
   - URL: `https://api.github.com/repos/tomasduer/core-bot/actions/workflows/reservar.yml/dispatches`
   - Método: **POST**
   - Horario: lunes a viernes **08:00**, zona `America/Argentina/Buenos_Aires`
   - Headers:
     - `Authorization`: `Bearer <EL_TOKEN>`
     - `Accept`: `application/vnd.github+json`
     - `Content-Type`: `application/json`
   - Body: `{"ref":"main","inputs":{"dry_run":"false"}}`
3. Probar con el botón de test del cronjob y verificar que en la pestaña
   **Actions** del repo aparezca una corrida nueva (evento `workflow_dispatch`).

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
   - `COREFIT_FIRE_TIME` (ej. `08:00`)
   - `COREFIT_BRANCH` (ej. `BELGRANO, ARCOS` — vacío usa la sucursal por defecto)
4. Repo → pestaña **Actions** → habilitá los workflows si te lo pide.

¡Listo! De lunes a viernes va a correr solo.

---

## 🧪 Probarlo sin reservar de verdad

### En GitHub (recomendado)
Repo → **Actions** → **Reservar clase CORE** → **Run workflow**.
Dejá `dry_run = true`: hace **todo el flujo menos el click final** de reservar.
Después mirá el log y descargá el artifact **screenshots**.

### En tu PC
```bash
pip install -r requirements.txt
python -m playwright install chromium

# copiá .env.example a .env y completá tus datos, luego:
python reservar.py --dry-run --now     # prueba todo, sin reservar
python reservar.py --now               # reserva YA (para el día +7)
python reservar.py                     # espera hasta las 08:00 y reserva
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

1. **Puntualidad del cron de GitHub.** Comprobado: dispara con 3-4,5 h de retraso.
   Mitigado con el disparador externo (cron-job.org) como principal y los crons
   internos como respaldo tardío.
2. **Errores transitorios del sitio** de madrugada. Mitigado con reintento
   automático (60s) dentro de cada corrida + disparos redundantes.
3. **Bloqueo de IP.** Verificado que hoy NO ocurre (Actions entra y reserva OK).
   Si algún día pasa, la alternativa es correr el bot en **tu propia PC** con el
   **Programador de tareas de Windows**. El mismo `reservar.py` sirve.

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
