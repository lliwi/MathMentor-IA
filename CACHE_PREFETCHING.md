# Cache Prefetching - MathMentor IA

## 🚀 Optimización de Prefetching de Caché

### ¿Qué es el Prefetching?

El **prefetching** (precarga) es una técnica de optimización que anticipa qué datos el usuario necesitará y los carga en caché **antes** de que sean solicitados.

### Implementación en MathMentor

Cuando un estudiante accede a `/student/practice`, el sistema automáticamente:

1. **Identifica los temas** asignados al estudiante
2. **Precarga en background** el contexto RAG de los primeros 3 temas
3. **Cachea los resultados** en Redis para uso inmediato
4. **No bloquea** la carga de la página (ejecuta en thread separado)

### Beneficios

#### Antes del Prefetching
```
Usuario accede a /practice -> Página carga (200ms)
Usuario genera ejercicio -> Busca contexto RAG (2-3s) + Genera ejercicio (5-8s) = 7-11s
```

#### Después del Prefetching
```
Usuario accede a /practice -> Página carga (200ms) + Prefetch en background (2-3s)
Usuario genera ejercicio -> Contexto desde cache (50ms) + Genera ejercicio (5-8s) = ~6s
```

**Mejora**: ~2-3 segundos más rápido en la primera generación

### Cómo Funciona

#### 1. Archivo: `app/student/routes.py`

```python
def _prefetch_contexts_background(app, topic_ids):
    """Background task to prefetch RAG contexts"""
    with app.app_context():
        try:
            rag_service = RAGService()
            # Prefetch context for first 3 topics (most likely to be used)
            for topic_id in topic_ids[:3]:
                # This will cache the context via @cache_service.cache_context decorator
                rag_service.get_context_for_topic(topic_id, top_k=3)
            print(f"[Practice] Prefetched RAG context for {min(3, len(topic_ids))} topics")
        except Exception as e:
            print(f"[Practice] Warning: Context prefetch failed: {e}")

@student_bp.route('/practice')
@student_required
def practice():
    """Practice area with prefetching"""
    stats = ScoringService.get_student_statistics(current_user.id)

    # Start prefetch in background thread
    profile = current_user.student_profile
    if profile:
        topic_ids = profile.get_topics()
        if topic_ids:
            app = current_app._get_current_object()
            thread = threading.Thread(target=_prefetch_contexts_background, args=(app, topic_ids))
            thread.daemon = True
            thread.start()

    return render_template('student/practice.html', stats=stats)
```

#### 2. ¿Por qué solo 3 temas?

- **Balance entre performance y recursos**
- La mayoría de estudiantes generan ejercicios de 2-3 temas por sesión
- Evita consumir demasiada memoria/CPU con prefetch innecesario
- Se pueden ajustar según necesidades

### Monitoreo

#### Ver Prefetching en Acción

```bash
# Ver logs de prefetch
docker-compose logs -f web | grep Practice

# Salida esperada:
[Practice] Started background prefetch for 2 topics
[Practice] Prefetched RAG context for 2 topics
```

#### Verificar Caché en Redis

```bash
# Ver keys cacheadas
docker-compose exec redis redis-cli KEYS "context:*"

# Ver cuántas keys hay
docker-compose exec redis redis-cli DBSIZE

# Ver contenido de una key
docker-compose exec redis redis-cli GET "context:abc123..."
```

### Configuración Avanzada

#### Ajustar Cantidad de Temas a Prefetch

En `app/student/routes.py`, línea 46:

```python
for topic_id in topic_ids[:3]:  # Cambiar 3 a otro número
```

#### Ajustar top_k de Chunks

En `app/student/routes.py`, línea 48:

```python
rag_service.get_context_for_topic(topic_id, top_k=3)  # Cambiar 3 a otro número
```

#### Desactivar Prefetching

Comentar el bloque de prefetch en `practice()`:

```python
@student_bp.route('/practice')
@student_required
def practice():
    stats = ScoringService.get_student_statistics(current_user.id)

    # # Prefetch disabled
    # try:
    #     profile = current_user.student_profile
    #     ...

    return render_template('student/practice.html', stats=stats)
```

### Consideraciones Técnicas

#### Threading en Flask

- Usamos `daemon threads` para que no impidan el shutdown de la app
- Pasamos `app context` explícitamente con `current_app._get_current_object()`
- Los errores en el thread no afectan la respuesta al usuario

#### Memory & Performance

**Impacto de Prefetching**:
- **CPU**: Mínimo (~1-2% por 2-3 segundos)
- **RAM**: ~10-20 MB temporales por prefetch
- **Red**: Query a PostgreSQL por cada tema
- **Redis**: ~5-10 KB por contexto cacheado

**Trade-offs**:
- ✅ Primera generación de ejercicio mucho más rápida
- ✅ Mejor experiencia de usuario
- ✅ No bloquea la carga de página
- ⚠️ Pequeño overhead en servidor
- ⚠️ Puede precachear temas no usados (pero TTL de 2h limita esto)

### Métricas de Éxito

#### KPIs a Monitorear

1. **Cache Hit Rate**: Porcentaje de contextos que vienen de caché
   ```bash
   # En logs, buscar proporción HIT vs MISS
   docker-compose logs web | grep "Cache HIT.*context" | wc -l
   docker-compose logs web | grep "Cache MISS.*context" | wc -l
   ```

2. **Tiempo de Primera Generación**: Tiempo desde que usuario entra a `/practice` hasta que ve su primer ejercicio

3. **Uso de Memoria Redis**: Monitorear crecimiento
   ```bash
   docker-compose exec redis redis-cli INFO memory
   ```

#### Valores Objetivo

- Cache Hit Rate: >70% (prefetch efectivo)
- Tiempo Primera Generación: <6 segundos
- Memoria Redis: <100 MB total

### Troubleshooting

#### Prefetch no aparece en logs

**Problema**: No ves `[Practice] Started background prefetch`

**Solución**:
1. Verificar que el estudiante tiene temas asignados
2. Verificar logs de error: `docker-compose logs web | grep Warning`
3. Verificar que el thread no falló silenciosamente

#### Contexto no se cachea

**Problema**: Siempre ves `Cache MISS for context`

**Solución**:
1. Verificar Redis está corriendo: `docker-compose exec redis redis-cli PING`
2. Verificar decorador en `RAGService.get_context_for_topic()`
3. Verificar TTL no ha expirado (default 2 horas)

#### Performance degradada

**Problema**: Página `/practice` carga lento

**Solución**:
1. Reducir cantidad de temas a prefetch (de 3 a 2 o 1)
2. Aumentar `top_k` en el prefetch (menos chunks)
3. Considerar desactivar prefetch en servidores con poca RAM

### Futuras Mejoras

#### Prefetching Inteligente

Usar ML para predecir qué temas el estudiante usará:

```python
# Basado en:
- Historial de ejercicios previos
- Tiempo del día
- Nivel de dificultad preferido
- Progreso en el curso
```

#### Prefetching Programado

Precachear durante horarios de baja carga:

```python
# Celery task que ejecuta cada hora
@celery.task
def scheduled_prefetch():
    # Precachear contextos de todos los estudiantes activos
    for student in active_students:
        prefetch_student_contexts(student.id)
```

#### Invalidación Inteligente

Invalidar caché cuando se actualiza el contenido:

```python
# Cuando admin sube nuevo PDF
@admin_bp.route('/upload-book', methods=['POST'])
def upload_book():
    # ... procesar PDF ...

    # Invalidar caché de temas afectados
    cache_service.clear_pattern(f"context:*")
```

## Referencias

- Implementación: [app/student/routes.py](app/student/routes.py:40-77)
- Cache Service: [app/services/cache_service.py](app/services/cache_service.py)
- RAG Service: [app/services/rag_service.py](app/services/rag_service.py:132-156)
