# Worship Multitrack App (Sistema Integral de Multitracks, Acordes y Proyección para Iglesia)

Bienvenido al repositorio central de **Worship Multitrack App**, una solución de grado profesional desarrollada en Python para la gestión y ejecución de pistas multitrack en vivo, sincronización de acordes y letras para músicos en tablets/teléfonos, y proyección dinámica de letras para las pantallas del templo/congregación.

---

## 🎯 Visión y Objetivos del Proyecto

1. **Reproducción y Mezcla Multitrack en Tiempo Real (PC/Host):**
   - Reproducción sincronizada de stems (Batería, Bajo, Guitarras, Teclados, Metrónomo/Click, Guía/Cues).
   - Mezcla individual por canal, mute/solo y asignación de salidas físicas (ej. Guía y Click a in-ears de músicos, banda al master estéreo).
2. **Terminal de Músicos en Tiempo Real (Android APK / Tablets / Navegadores LAN):**
   - Pantalla interactiva con acordes y letra sincronizada con el cursor de tiempo del multitrack.
   - Modos de transposición instantánea de tono y cifrado (C, D, E o sistema de números de Nashville).
   - Auto-scroll adaptativo según la posición actual de la canción (Intro, Verso, Coro, Puente, etc.).
3. **Módulo de Proyección para Pantallas del Público:**
   - Salida limpia solo de letras en tiempo real a pantallas secundarias, proyectores o software de transmisión (OBS / vMix / HDMI).
   - Fondo personalizable, tipografías legibles y sincronización milimétrica para que la congregación cante en el tiempo exacto.
4. **Desarrollo en Python y Compilación Multiplataforma:**
   - Motor central y backend en scripts de Python.
   - Distribución para PC (Windows ejecutable / script local) y APKs para Android para los dispositivos de los músicos.

---

## 📂 Estructura del Repositorio

```text
worship-multitrack-app/
├── .agents/                        # Equipo autónomo de subagentes y skills de desarrollo
│   ├── skills.md                   # Catálogo maestro de habilidades técnicas y de dominio
│   ├── 00-team-overview.md         # Manifiesto y flujo de trabajo del equipo
│   ├── 01-lead-architect.md        # Arquitecto de Software & Tech Lead
│   ├── 02-audio-multitrack-engineer.md # Especialista en Motor de Audio y Stems
│   ├── 03-network-sync-engineer.md # Ingeniero de Sincronización en Red y WebSockets
│   ├── 04-musician-ui-frontend-dev.md  # Desarrollador UI Músicos (Acordes + Letras)
│   ├── 05-projection-screen-dev.md     # Desarrollador de Proyección / Pantalla Pública
│   ├── 06-android-mobile-dev.md    # Ingeniero de Empaquetado APK & Móvil Android
│   ├── 07-qa-testing-engineer.md   # Ingeniero de Pruebas de Latencia y Estabilidad
│   ├── 08-devops-docs-deliverables.md  # Encargado de Entregables, Docs y Build Scripts
│   └── 09-handover-sync-agent.md   # Agente de Relevo, Sincronización y Git
├── deliverables/                   # Carpeta oficial de entregables del proyecto
│   ├── README.md                   # Índice de entregables generados
│   ├── architecture/               # Diagramas, especificaciones y RFCs
│   ├── builds/                     # Paquetes compilados, ejecutables y APKs
│   └── docs/                       # Manuales de usuario, guías de operación y APIs
├── src/                            # Código fuente modular en Python
│   ├── audio/                      # Motor de reproducción, mezcla y manejo de stems
│   ├── core/                       # Estructuras de datos, reloj maestro de sincronización
│   ├── server/                     # Servidor HTTP/WebSocket para red local
│   ├── clients/                    # Clientes de visualización (Músicos y Proyección)
│   └── utils/                      # Parsers (ChordPro, LRC, JSON) y utilidades
├── tracks/                         # Carpeta de almacenamiento de canciones y multitracks
├── config/                         # Archivos de configuración de audio y red
├── HANDOVER.md                     # Registro de relevo de turnos entre desarrolladores
├── PROJECT_SPEC.md                 # Especificación técnica detallada
└── requirements.txt                # Dependencias del ecosistema Python
```

---

## 👥 Equipo de Subagentes (.agents/)

El desarrollo de este sistema está orquestado por un equipo de 9 subagentes especializados, cada uno con directrices YAML, instrucciones generales y tareas individuales dentro de `.agents/`:

| Subagente | Rol Principal |
| :--- | :--- |
| **01-lead-architect** | Arquitectura del sistema, modelo de datos y diseño modular. |
| **02-audio-multitrack-engineer** | Motor de audio multicanal en Python, clock master y control de stems. |
| **03-network-sync-engineer** | Servidor local de baja latencia, broadcast WebSocket y descubrimiento LAN. |
| **04-musician-ui-frontend-dev** | Interfaz para tablets/teléfonos: acordes, letras y transposición. |
| **05-projection-screen-dev** | Interfaz limpia para pantallas del templo y compatibilidad HDMI/OBS. |
| **06-android-mobile-dev** | Empaquetado para Android (APK), soporte offline y consumo de red. |
| **07-qa-testing-engineer** | Pruebas de estrés, sincronización de reloj y tolerancia a fallos. |
| **08-devops-docs-deliverables** | Generación de entregables, manuales de usuario y scripts de despliegue. |
| **09-handover-sync-agent** | Relevos entre turnos, control de continuidad en `HANDOVER.md` y sincronización Git. |

Para consultar las habilidades compartidas del equipo, revise [.agents/skills.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/skills.md).
