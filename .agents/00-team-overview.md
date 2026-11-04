---
name: team-overview
title: Manifiesto de Operaciones y Flujo de Trabajo del Equipo de Subagentes
version: 1.1.0
project: Worship Multitrack App
created_at: 2026-11-04
---

# 👥 Manifiesto de Operaciones del Equipo (.agents/00-team-overview.md)

Este documento define la estructura colaborativa, roles y ciclo de vida de desarrollo del equipo de subagentes especializados para **Worship Multitrack App**.

---

## 🎯 Organigrama del Equipo

```
                     ┌────────────────────────────────┐
                     │      01-lead-architect         │
                     │  (Dirección Técnica & Sistema) │
                     └───────────────┬────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐        ┌──────────────────┐
│02-audio-multitrack│      │03-network-sync   │        │04-musician-ui    │
│  (Motor de Audio)│       │  (WebSockets LAN)│        │ (Acordes & Letras│
└────────┬─────────┘       └─────────┬────────┘        └─────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐        ┌──────────────────┐
│05-projection-    │       │06-android-mobile │        │07-qa-testing     │
│screen-dev        │       │-dev (Build APKs) │        │ (Latencia & Sync)│
└──────────────────┘       └──────────────────┘        └──────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
           ┌──────────────────┐            ┌──────────────────┐
           │08-devops-docs-   │            │09-handover-sync- │
           │deliverables      │            │agent (Relevos)   │
           └──────────────────┘            └──────────────────┘
```

---

## 📋 Catálogo de Subagentes

1. **[01-lead-architect.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/01-lead-architect.md)**
   - **Misión:** Diseñar la arquitectura integral, definir contratos de interfaces, coordinar dependencias entre módulos y garantizar que las soluciones cumplan con los requerimientos del usuario.
2. **[02-audio-multitrack-engineer.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/02-audio-multitrack-engineer.md)**
   - **Misión:** Desarrollar el motor de audio en Python para reproducción sincronizada de stems (stems mixer), ruteo de canales (Sala vs Auriculares Músicos) y reloj maestro.
3. **[03-network-sync-engineer.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/03-network-sync-engineer.md)**
   - **Misión:** Construir el servidor local (FastAPI/WebSockets), autodescubrimiento LAN (mDNS/UDP) y el protocolo de sincronización de reloj con baja latencia.
4. **[04-musician-ui-frontend-dev.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/04-musician-ui-frontend-dev.md)**
   - **Misión:** Implementar la interfaz visual para músicos en tablets y teléfonos (acordes sincronizados con la pista, teleprompter, transposición de tono y modo oscuro de escenario).
5. **[05-projection-screen-dev.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/05-projection-screen-dev.md)**
   - **Misión:** Desarrollar la pantalla de proyección limpia para el templo (solo letras de congregación, lower-thirds para streaming y transiciones suaves de estrofas).
6. **[06-android-mobile-dev.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/06-android-mobile-dev.md)**
   - **Misión:** Configurar y compilar la aplicación para dispositivos Android en formato APK, optimizando el consumo de energía y manteniendo la pantalla activa durante el culto.
7. **[07-qa-testing-engineer.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/07-qa-testing-engineer.md)**
   - **Misión:** Ejecutar pruebas de estrés, pruebas de carga con múltiples clientes conectados, validación de sincronización milimétrica y prevención de cortes de audio.
8. **[08-devops-docs-deliverables.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/08-devops-docs-deliverables.md)**
   - **Misión:** Gestionar la carpeta `deliverables/`, redactar manuales claros en español, preparar scripts de ejecución con un solo clic y documentar cada versión.
9. **[09-handover-sync-agent.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/09-handover-sync-agent.md)**
   - **Misión:** Garantizar la continuidad operativa entre turnos de desarrolladores, gestionar el archivo `HANDOVER.md`, registrar cierres e inicios de turno y coordinar commits y pushes a GitHub.

---

## 🔄 Protocolo de Colaboración

- Cada agente consulta [skills.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/skills.md) como referencia de capacidades.
- Todo cambio arquitectónico debe ser validado por el **01-lead-architect**.
- Los relevos entre sesiones de desarrollo los lidera **09-handover-sync-agent**.
- Los entregables finales siempre se depositan y documentan en la carpeta [deliverables/](file:///C:/Users/palva/Desktop/worship-multitrack-app/deliverables/).
- Toda la base de código debe mantenerse en español para nombres de conceptos de dominio (acordes, pistas, guías, pantalla pública) y en inglés estándar para convenciones de código (variables, funciones, clases).
