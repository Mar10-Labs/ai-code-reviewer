# Changelog

Todos los cambios significativos del proyecto se documentan aquí.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [Unreleased]

### Added
- Cola asíncrona con asyncio.Queue para procesar eventos en background
- Sistema de idempotencia con deduplicación por delivery_id
- EventStore con SQLite para persistencia de eventos
- Worker que procesa la cola con retry automático (max 3 intentos)
- Endpoint `/agent/webhook/github` para recibir eventos de GitHub
- Endpoint `/agent/queue/status` para monitorear la cola
- Tests para el sistema de cola (10 tests nuevos)

## [1.0.0] - 2026-03-20

### Added
- 5 agentes especializados de code review (CodeQuality, Performance, Security, Documentation, Testing)
- MasterAgent con LangGraph para orquestación
- Arquitectura hexagonal con adapters para Groq, Gemini, Ollama
- API endpoints para revisión de PRs
- 9 agentes de guía en `.agents/` para desarrollo del proyecto

### Changed
- Arquitectura refactorizada para enfocarse en code review automático
- Implementación de LangGraph para orquestación de agentes

### Removed
- DevOpsAgent (no alineado con el objetivo de code review)
- GitService (operaciones git fuera del scope)

### Fixed
- Tests actualizados para nueva arquitectura

### Security
- Prompt injection detection básico

---

## [0.1.0] - 2026-03-19

### Added
- Estructura base del proyecto
- Modelos Pydantic para schemas
- Tests de integración
- Soporte Docker
- Configuración inicial de LLM adapters
