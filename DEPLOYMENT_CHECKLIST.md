# 🚀 Deployment Checklist - Performance Optimizations

## ✅ Pre-Deployment Checklist

### 1. Verificar Archivos Modificados

- [x] `app/services/rag_service.py` - Singleton + Embedding cache + Batch processing
- [x] `app/services/cache_service.py` - Nuevo servicio de caché con Redis
- [x] `app/ai_engines/openai_engine.py` - Cache decorator agregado
- [x] `app/ai_engines/deepseek_engine.py` - Cache decorator agregado
- [x] `app/ai_engines/ollama_engine.py` - Cache decorator agregado
- [x] `app/__init__.py` - Connection pooling configurado
- [x] `docker-compose.yml` - Redis container agregado
- [x] `requirements.txt` - Dependencias redis y cachetools agregadas
- [x] `.env` - Variables de Redis agregadas
- [x] `add_indexes.py` - Script para crear índices (nuevo)
- [x] `PERFORMANCE_OPTIMIZATIONS.md` - Documentación completa (nuevo)
- [x] `README.md` - Actualizado con instrucciones

## 🔧 Deployment Steps

### Paso 1: Backup de Datos (IMPORTANTE)

```bash
# Backup de la base de datos
docker-compose exec db pg_dump -U mathmentor_user mathmentor > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup de archivos subidos
tar -czf uploads_backup_$(date +%Y%m%d_%H%M%S).tar.gz uploads/
```

### Paso 2: Detener Servicios

```bash
docker-compose down
```

### Paso 3: Actualizar Código

```bash
git pull origin main
# O copiar los archivos modificados manualmente
```

### Paso 4: Construir y Levantar Servicios

```bash
# Construir imagen con nuevas dependencias
docker-compose build --no-cache

# Levantar servicios
docker-compose up -d

# Verificar que todos los servicios están corriendo
docker-compose ps
```

**Verificar que aparezcan 3 servicios:**
- `mathmentor_db` (PostgreSQL)
- `mathmentor_redis` (Redis)
- `mathmentor_web` (Flask)

### Paso 5: Aplicar Índices de Performance ⚡

```bash
# Esperar 30 segundos a que los servicios estén listos
sleep 30

# Ejecutar script de índices
docker-compose exec web python add_indexes.py
```

**Salida esperada:**
```
============================================================
🔧 Adding Performance Indexes
============================================================

📊 Creating HNSW index for vector similarity search...
   (This may take a few minutes for large datasets)
   ✅ HNSW index created

📊 Creating composite indexes...
   ✅ idx_embeddings_book_page created on document_embeddings
   ✅ idx_embeddings_book_id created on document_embeddings
   ✅ idx_exercises_topic created on exercises
   ...

============================================================
✅ Performance indexes added successfully!
============================================================
```

### Paso 6: Verificar Redis

```bash
# Verificar que Redis está corriendo
docker-compose exec redis redis-cli ping

# Debe responder: PONG
```

### Paso 7: Verificar Logs

```bash
# Ver logs de la aplicación
docker-compose logs web | tail -50

# Buscar mensajes de inicialización
docker-compose logs web | grep -i "RAGService\|CacheService"
```

**Mensajes esperados:**
```
[RAGService] Initializing singleton with model: sentence-transformers/all-MiniLM-L6-v2
[RAGService] Model loaded successfully, embedding dimension: 384
[CacheService] Connected to Redis at redis:6379
```

### Paso 8: Probar Funcionalidad

```bash
# Acceder a la aplicación
http://localhost:5000

# Como estudiante:
# 1. Login con maria/estudiante123
# 2. Generar ejercicio (primera vez: MISS)
# 3. Generar otro ejercicio del mismo tema (segunda vez: HIT esperado)
```

### Paso 9: Verificar Caché Funcionando

```bash
# Ver logs en tiempo real
docker-compose logs -f web

# Buscar mensajes de caché
# Cache MISS: Primera generación
# Cache HIT: Generaciones subsecuentes con mismos parámetros
```

**Ejemplo de salida:**
```
[CacheService] Cache MISS for exercise: exercise:abc123def...
[CacheService] Cache HIT for exercise: exercise:abc123def...
[CacheService] Cache HIT for context: context:xyz789...
```

## 🧪 Testing

### Test 1: Generación de Ejercicio con Caché

```bash
# Primera generación (cache MISS)
time curl -X POST http://localhost:5000/student/generate-exercise \
  -H "Content-Type: application/json" \
  -d '{"difficulty": "medium"}' \
  -b cookies.txt

# Segunda generación (cache HIT - debería ser mucho más rápido)
time curl -X POST http://localhost:5000/student/generate-exercise \
  -H "Content-Type: application/json" \
  -d '{"difficulty": "medium"}' \
  -b cookies.txt
```

### Test 2: Verificar Índices

```bash
docker-compose exec db psql -U mathmentor_user -d mathmentor -c "\di+"
```

**Debe mostrar:**
- `idx_embeddings_hnsw` - HNSW index para vectores
- `idx_embeddings_book_page` - Índice compuesto
- `idx_exercises_topic` - Índice para ejercicios
- etc.

### Test 3: Estadísticas de Redis

```bash
# Ver estadísticas de Redis
docker-compose exec redis redis-cli INFO stats

# Ver keys cacheadas
docker-compose exec redis redis-cli KEYS "*"

# Ver contenido de una key (ejemplo)
docker-compose exec redis redis-cli GET "exercise:abc123..."
```

## 📊 Monitoring

### Métricas Clave a Monitorear

1. **Tasa de Cache Hit/Miss**
   ```bash
   docker-compose logs web | grep -c "Cache HIT"
   docker-compose logs web | grep -c "Cache MISS"
   ```

2. **Memoria de Redis**
   ```bash
   docker-compose exec redis redis-cli INFO memory
   ```

3. **Tamaño de Índices**
   ```bash
   docker-compose exec db psql -U mathmentor_user -d mathmentor -c "
   SELECT pg_size_pretty(pg_relation_size('idx_embeddings_hnsw'));
   "
   ```

4. **Conexiones de PostgreSQL**
   ```bash
   docker-compose exec db psql -U mathmentor_user -d mathmentor -c "
   SELECT count(*) FROM pg_stat_activity WHERE datname='mathmentor';
   "
   ```

## 🔄 Rollback Plan

Si algo sale mal:

### Opción 1: Rollback Rápido (sin cambios en DB)

```bash
# Detener servicios
docker-compose down

# Checkout a versión anterior
git checkout <previous-commit>

# Levantar con configuración anterior
docker-compose up -d
```

### Opción 2: Rollback Completo (con restauración de DB)

```bash
# Detener servicios
docker-compose down

# Restaurar backup de base de datos
docker-compose up -d db
docker-compose exec -T db psql -U mathmentor_user -d mathmentor < backup_YYYYMMDD_HHMMSS.sql

# Restaurar código anterior
git checkout <previous-commit>
docker-compose up -d
```

## ⚠️ Troubleshooting

### Redis no conecta

**Síntoma:**
```
[CacheService] Warning: Redis not available (Connection refused). Caching disabled.
```

**Solución:**
```bash
docker-compose ps redis
docker-compose restart redis
docker-compose logs redis
```

### Índices no se crean

**Síntoma:**
```
ERROR: could not create unique index "idx_embeddings_hnsw"
```

**Solución:**
```bash
# Verificar extensión pgvector
docker-compose exec db psql -U mathmentor_user -d mathmentor -c "
SELECT * FROM pg_extension WHERE extname='vector';
"

# Si no existe, crear
docker-compose exec db psql -U mathmentor_user -d mathmentor -c "
CREATE EXTENSION IF NOT EXISTS vector;
"

# Reintentar índices
docker-compose exec web python add_indexes.py
```

### Modelo de embeddings no carga

**Síntoma:**
```
[RAGService] Error loading model...
```

**Solución:**
```bash
# Verificar espacio en disco
df -h

# Descargar modelo manualmente
docker-compose exec web python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Model loaded successfully')
"
```

### Performance no mejora

**Checklist:**
1. [ ] Redis está corriendo: `docker-compose ps redis`
2. [ ] Índices creados: `docker-compose exec web python add_indexes.py`
3. [ ] Logs muestran cache hits: `docker-compose logs web | grep "Cache HIT"`
4. [ ] Connection pool configurado: Verificar [app/__init__.py](app/__init__.py)

## 🎯 Success Criteria

Las optimizaciones están funcionando correctamente si:

- [x] Redis responde a PING
- [x] Logs muestran "RAGService singleton initialized"
- [x] Logs muestran "CacheService connected to Redis"
- [x] Script add_indexes.py completa exitosamente
- [x] Segunda generación de ejercicio es significativamente más rápida
- [x] Logs muestran "Cache HIT" en requests subsecuentes
- [x] No hay errores en `docker-compose logs`

## 📞 Support

Si encuentras problemas:

1. Revisar logs: `docker-compose logs --tail=100`
2. Consultar [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)
3. Verificar sección Troubleshooting arriba
4. Crear issue en el repositorio con logs completos

## 📝 Notas Finales

- **Redis es opcional**: Si Redis falla, la app funciona sin caché
- **Índices son cruciales**: El índice HNSW es el que más impacto tiene
- **Primera carga es lenta**: El modelo de embeddings tarda 2-5s en cargar (una sola vez)
- **Monitorear memoria**: Redis y el modelo de embeddings consumen ~500MB RAM adicional
