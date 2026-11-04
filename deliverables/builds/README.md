# 🏗️ Compilaciones y Binarios Distribuidos (deliverables/builds/)

Este directorio está destinado a almacenar los paquetes compilados y listos para distribución del proyecto **Worship Multitrack App**.

---

## 📱 Subcarpeta: `android/`
- **Destino:** Archivos `.apk` para instalación en tablets y teléfonos Android.
- **Responsable:** Subagente `06-android-mobile-dev`.
- **Formatos:**
  - `worship-musician-v1.0.0-universal.apk` (Compilación universal para arquitecturas ARM64 y x86).
  - Manual de instalación en Android (*sideloading* habilitando orígenes desconocidos).

---

## 💻 Subcarpeta: `pc/`
- **Destino:** Paquetes ejecutables y utilitarios para computadoras con Windows en la cabina de sonido.
- **Responsable:** Subagente `08-devops-docs-deliverables`.
- **Formatos:**
  - `start_app.bat` (Lanzador con detección automática de entorno virtual).
  - `worship-host-win64.zip` (Paquete portable autocontenido con Python embebido).
