#!/bin/bash

# ===============================================
# NUCLEAR PROJECT CLEANUP - Solo tu proyecto
# ===============================================
# Elimina TODO relacionado con este docker-compose.yaml
# pero mantiene otros proyectos Docker intactos
# ===============================================

# Obtener el nombre del proyecto (directorio actual)
PROJECT_NAME=$(basename "$(pwd)")
COMPOSE_FILE="docker-compose.yaml"

echo "🎯 =========================================="
echo "🎯 LIMPIEZA NUCLEAR DEL PROYECTO: $PROJECT_NAME"
echo "🎯 =========================================="
echo ""
echo "🔥 Este script eliminará SOLO los recursos de este proyecto:"
echo "   • Contenedores: airflow_*, postgres, minio, mlflow, fastapi"
echo "   • Imágenes: extending_airflow, postgres_system, mlflow, backend_fastapi"
echo "   • Volúmenes: ${PROJECT_NAME}_db_data, ${PROJECT_NAME}_minio_data"
echo "   • Redes: ${PROJECT_NAME}_frontend, ${PROJECT_NAME}_backend"
echo ""
echo "✅ Se conservarán:"
echo "   • Otros proyectos Docker"
echo "   • Imágenes base (python, postgres, minio/minio, etc.)"
echo "   • Tu código fuente"
echo ""
echo -n "¿Continuar? (y/N): "
read -r confirmation

if [[ ! "$confirmation" =~ ^[Yy]$ ]]; then
    echo "❌ Operación cancelada."
    exit 0
fi

echo ""
echo "🔥 Iniciando limpieza del proyecto $PROJECT_NAME..."
echo ""

# 1. Parar y eliminar servicios del docker compose
echo "🛑 Deteniendo servicios del proyecto..."
if [ -f "$COMPOSE_FILE" ]; then
    docker compose --profile all down -v --remove-orphans 2>/dev/null || echo "   ℹ️  Algunos servicios ya estaban detenidos"
else
    echo "   ⚠️  No se encontró $COMPOSE_FILE en el directorio actual"
fi

# 2. Eliminar contenedores específicos del proyecto (por si quedan huérfanos)
echo "🗑️  Eliminando contenedores del proyecto..."
PROJECT_CONTAINERS=$(docker ps -aq --filter "name=airflow_" --filter "name=postgres" --filter "name=minio" --filter "name=mlflow" --filter "name=fastapi")
if [ -n "$PROJECT_CONTAINERS" ]; then
    echo "   Eliminando: $(echo $PROJECT_CONTAINERS | tr '\n' ' ')"
    docker rm -f $PROJECT_CONTAINERS 2>/dev/null || true
else
    echo "   ℹ️  No hay contenedores del proyecto que eliminar"
fi

# 3. Eliminar imágenes específicas del proyecto
echo "🖼️  Eliminando imágenes del proyecto..."
PROJECT_IMAGES="extending_airflow:latest postgres_system:latest mlflow:latest backend_fastapi:latest"
for image in $PROJECT_IMAGES; do
    if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^$image$"; then
        echo "   Eliminando imagen: $image"
        docker rmi "$image" 2>/dev/null || echo "   ⚠️  No se pudo eliminar $image (puede estar en uso)"
    else
        echo "   ℹ️  Imagen $image no encontrada"
    fi
done

# 4. Eliminar volúmenes específicos del proyecto
echo "📦 Eliminando volúmenes del proyecto..."
PROJECT_VOLUMES="${PROJECT_NAME}_db_data ${PROJECT_NAME}_minio_data"
for volume in $PROJECT_VOLUMES; do
    if docker volume ls --format "{{.Name}}" | grep -q "^$volume$"; then
        echo "   Eliminando volumen: $volume"
        docker volume rm "$volume" 2>/dev/null || echo "   ⚠️  No se pudo eliminar $volume"
    else
        echo "   ℹ️  Volumen $volume no encontrado"
    fi
done

# 5. Eliminar redes específicas del proyecto
echo "🌐 Eliminando redes del proyecto..."
PROJECT_NETWORKS="${PROJECT_NAME}_frontend ${PROJECT_NAME}_backend ${PROJECT_NAME}_default"
for network in $PROJECT_NETWORKS; do
    if docker network ls --format "{{.Name}}" | grep -q "^$network$"; then
        echo "   Eliminando red: $network"
        docker network rm "$network" 2>/dev/null || echo "   ℹ️  Red $network en uso o ya eliminada"
    else
        echo "   ℹ️  Red $network no encontrada"
    fi
done

# 6. Limpiar recursos no utilizados (solo los que no tienen referencias)
echo "🧹 Limpieza de recursos huérfanos..."
docker system prune -f 2>/dev/null || true

echo ""
echo "✅ ¡LIMPIEZA DEL PROYECTO COMPLETADA!"
echo ""
echo "📊 Estado actual del proyecto:"
echo ""

# Verificar que todo se eliminó
echo "🔍 Verificando contenedores del proyecto:"
REMAINING_CONTAINERS=$(docker ps -a --filter "name=airflow_" --filter "name=postgres" --filter "name=minio" --filter "name=mlflow" --filter "name=fastapi" --format "{{.Names}}")
if [ -n "$REMAINING_CONTAINERS" ]; then
    echo "   ⚠️  Contenedores restantes: $REMAINING_CONTAINERS"
else
    echo "   ✅ No hay contenedores del proyecto"
fi

echo ""
echo "🔍 Verificando imágenes del proyecto:"
REMAINING_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "(extending_airflow|postgres_system|mlflow|backend_fastapi)")
if [ -n "$REMAINING_IMAGES" ]; then
    echo "   ⚠️  Imágenes restantes:"
    echo "$REMAINING_IMAGES" | sed 's/^/      /'
else
    echo "   ✅ No hay imágenes del proyecto"
fi

echo ""
echo "🔍 Verificando volúmenes del proyecto:"
REMAINING_VOLUMES=$(docker volume ls --format "{{.Name}}" | grep "$PROJECT_NAME")
if [ -n "$REMAINING_VOLUMES" ]; then
    echo "   ⚠️  Volúmenes restantes: $REMAINING_VOLUMES"
else
    echo "   ✅ No hay volúmenes del proyecto"
fi

echo ""
echo "🔄 Para reconstruir el proyecto:"
echo "   docker compose --profile all up -d --build"
echo ""
echo "⏱️  La primera ejecución será más lenta porque debe"
echo "   reconstruir las imágenes personalizadas del proyecto."
