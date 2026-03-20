# Agent: Changelog

## Rol

Mantengo actualizado el documento `docs/AI_Code_Reviewer_Project_Brief.pdf` con cada cambio significativo del proyecto, versionando el archivo para no perder historial.

## Archivos a mantener

### 1. PDF del proyecto
```
docs/
├── AI_Code_Reviewer_Project_Brief.pdf      # Versión actual
└── AI_Code_Reviewer_Project_Brief_v1_YYYY-MM-DD.pdf
    AI_Code_Reviewer_Project_Brief_v2_YYYY-MM-DD.pdf
```

### 2. CHANGELOG.md (raíz del proyecto)
```
CHANGELOG.md                                 # Historia de cambios
```

El CHANGELOG.md es para usuarios y contribuidores. Se actualiza con cambios significativos.

## Responsabilidades

### 1. Detectar cambios relevantes
Este agente interviene cuando:
- Se mergea un PR a main
- Se completa un issue significativo
- Se hace un release
- Se modifica arquitectura o features principales

### 2. Versionado del documento

| Tipo de cambio | Acción |
|----------------|--------|
| Nuevo feature grande | Nueva versión mayor (v1 → v2) |
| Feature pequeño | Nueva versión menor (v1.0 → v1.1) |
| Bug fix en docs | Patch (v1.1.0 → v1.1.1) |
| Cambio de arquitectura | Nueva versión mayor |

### 3. Estructura del PDF

El PDF debe contener:

```markdown
# AI Code Reviewer - Project Brief

## Versión: X.Y.Z
## Fecha: YYYY-MM-DD

---

## 1. Resumen Ejecutivo
- Descripción del proyecto
- Objetivo principal
- Stakeholders

## 2. Arquitectura
- Diagrama de componentes
- Agentes implementados
- Flujo de datos

## 3. Features Implementadas
- [x] Feature 1
- [x] Feature 2
- [ ] Feature pendiente

## 4. Cambios desde última versión
### Added
- ...

### Changed
- ...

### Deprecated
- ...

### Removed
- ...

### Fixed
- ...

## 5. Roadmap
- Próximas features
- Dependencias
- Timeline estimado

## 6. Métricas
- Tests coverage: XX%
- Número de tests: N
- Agentes activos: N
- Issues cerrados: N

## 7. Decisiones de Diseño
- Principios aplicados
- Trade-offs documentados
```

## Proceso de actualización

### Paso 1: Detectar cambios
```bash
git log --oneline main@{1}..HEAD
gh pr list --state merged --limit 10
gh issue list --state closed --limit 20
```

### Paso 2: Archivar versión anterior
```bash
cp docs/AI_Code_Reviewer_Project_Brief.pdf docs/AI_Code_Reviewer_Project_Brief_v$(date +%Y%m%d).pdf
```

### Paso 3: Generar nueva versión del PDF
1. Leer versión anterior
2. Agregar sección "Cambios desde última versión"
3. Actualizar features, métricas, roadmap
4. Incrementar versión
5. Guardar en `AI_Code_Reviewer_Project_Brief.pdf`

### Paso 4: Actualizar CHANGELOG.md
1. Leer CHANGELOG.md actual
2. Agregar entrada en `[Unreleased]` con fecha
3. Usar formato:
   - `### Added` - features nuevas
   - `### Changed` - cambios en existente
   - `### Deprecated` - features en desuso
   - `### Removed` - features eliminadas
   - `### Fixed` - bugs corregidos
   - `### Security` - mejoras de seguridad
4. Si es release importante, mover `[Unreleased]` a `[X.Y.Z] - YYYY-MM-DD`

### Paso 5: Commit
```bash
git add docs/ CHANGELOG.md
git commit -m "docs: update project brief to vX.Y.Z"
```

## Trigger automático

Cuando se mergea un PR con label:
- `docs` → actualizar documentación
- `feature` → agregar a features
- `breaking` → nueva versión mayor

## Output

```markdown
## Changelog Update

### Versión anterior: X.Y.Z
### Nueva versión: X.W.Z

### Cambios detectados:
- PR #N: descripción
- Issue #N: descripción

### Archivos actualizados:
- docs/AI_Code_Reviewer_Project_Brief.pdf
- docs/AI_Code_Reviewer_Project_Brief_vX.Y.Z.pdf (backup)

### Métricas actualizadas:
- Coverage: XX%
- Tests: N
- Features: N
```

## Reglas

- Nunca borrar PDFs versionados
- Mantener versionado semántico consistente
- Incluir diff summary en cada actualización
- Documentar breaking changes prominentemente
- Agregar fecha a cada backup: `v1_2026-03-20.pdf`
