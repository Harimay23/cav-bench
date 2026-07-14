from __future__ import annotations


class CavBenchError(Exception):
    """Base class for all CAV-Bench errors."""


class SchemaValidationError(CavBenchError):
    """A scenario, trace, or evaluation document failed schema validation."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message
        super().__init__(f"{source}: {message}")


class ScenarioLoadError(CavBenchError):
    """A scenario pack or scenario file could not be loaded or is semantically invalid."""


class UnsupportedSchemaVersion(CavBenchError):
    """A document declares a schema_version this build of CAV-Bench does not support."""

    def __init__(self, source: str, found: str, supported: str) -> None:
        self.source = source
        self.found = found
        self.supported = supported
        super().__init__(
            f"{source}: schema_version {found!r} is not supported (expected {supported!r})"
        )


class VersionConflict(CavBenchError):
    """A mutation was attempted against a stale expected_version."""


class ResourceNotFound(CavBenchError):
    """A namespace/resource_id pair does not exist in authoritative state."""


class AdapterProtocolError(CavBenchError):
    """An execution adapter violated the adapter/tool-facade contract."""


class RunConfigError(CavBenchError):
    """A run configuration or CLI invocation is invalid."""
