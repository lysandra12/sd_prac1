#!/bin/bash
# Limpia el estado de Redis antes de cada benchmark.
# Ejecutar en la instancia Redis (o desde cualquier maquina con acceso).
REDIS_HOST=${1:-localhost}

redis-cli -h "$REDIS_HOST" FLUSHDB
redis-cli -h "$REDIS_HOST" SET total_sold 0
echo "Redis reseteado en $REDIS_HOST"
