# Quick Start Guide - MathMentor IA

## 🚀 Inicio Rápido (5 minutos)

### 1. Configuración Inicial

```bash
# Clonar y entrar al directorio
cd "MathMentor IA"

# Copiar archivo de configuración
cp .env.example .env
```

### 2. Editar `.env`

Configura al menos una clave API:

```env
# Para usar OpenAI
OPENAI_API_KEY=tu-clave-aqui
ACTIVE_AI_ENGINE=openai

# O para usar DeepSeek
DEEPSEEK_API_KEY=tu-clave-aqui
ACTIVE_AI_ENGINE=deepseek

# O para usar Ollama (local, sin clave)
ACTIVE_AI_ENGINE=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Iniciar la Aplicación

```bash
# Iniciar servicios
docker-compose up -d

# La base de datos se inicializa automáticamente en el primer arranque
# Si ves usuarios de prueba creados en los logs, ¡ya está listo!
```

**Nota**: La aplicación detecta automáticamente si es una instalación nueva y crea:
- Usuario administrador: `admin` / `admin123`
- Usuarios estudiantes de prueba: `maria`, `juan`, `lucia` / `estudiante123`

### 4. Acceder

Abrir navegador en: **http://localhost:5000**

**Usuarios de prueba:**
- Admin: `admin` / `admin123`
- Estudiante: `maria` / `estudiante123`

---

## 📖 Flujo de Uso Completo

### Como Administrador:

1. **Login** con admin/admin123
2. **Ir a "Libros" → "Subir Nuevo Libro"**
3. Completar formulario y subir PDF
4. Esperar procesamiento (se extraen temas automáticamente)
5. **Ir a "Estudiantes"** → Seleccionar estudiante → "Asignar Temas"
6. Elegir curso y marcar temas asignados

### Como Estudiante:

1. **Login** con maria/estudiante123
2. **Ir a "Practicar"**
3. Seleccionar dificultad → "Generar Ejercicio"
4. Resolver y escribir procedimiento
5. "Enviar Respuesta"
6. Ver feedback y puntos obtenidos
7. **Ir a "Marcador"** para ver progreso

---

## 🎮 Sistema de Puntos

- ✅ **+10 puntos**: Respuesta correcta
- 📝 **+5 puntos**: Metodología correcta
- 🔄 **+3 puntos**: Reintento exitoso
- 🔥 **Bonus**: Rachas de 3, 5, 10, 15+ ejercicios
- 💡 **-5 puntos**: Comprar una pista

---

## 🛠️ Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f web

# Reiniciar aplicación
docker-compose restart web

# Detener todo
docker-compose down

# Ver estado de servicios
docker-compose ps
```

---

## ❌ Problemas Comunes

### "No hay libros procesados"
→ Asegúrate de subir un PDF desde el panel de admin primero

### "No tienes temas asignados"
→ El administrador debe asignar temas al estudiante

### "Error al generar ejercicio"
→ Verifica que tu clave API esté configurada correctamente en `.env`

### Error de conexión BD
→ Ejecuta: `docker-compose restart db`

---

## 📚 Más Información

- **Documentación completa**: Ver [README.md](README.md)
- **Detalles técnicos**: Ver [CLAUDE.md](CLAUDE.md)
- **Especificación original**: Ver [MathMentor IA.md](MathMentor IA.md)

---

## 🔒 Seguridad

⚠️ **IMPORTANTE**: Cambia las contraseñas de prueba antes de usar en producción.

Las credenciales actuales son solo para desarrollo y testing.
