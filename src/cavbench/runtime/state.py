"""Versioned authoritative state store with optimistic concurrency.

Resources are addressed by ``(namespace, resource_id)``. Every mutable
resource carries an integer ``version``. A mutation may supply
``expected_version``; if it does not match the resource's current version the
mutation is rejected with :class:`~cavbench.errors.VersionConflict` and no
state changes. Mutations that omit ``expected_version`` always proceed --
this is what lets an unguarded execution strategy commit against stale data,
which is the behavior CAV-Bench's temporal-state-validity dimension exists to
catch.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from cavbench.errors import ResourceNotFound
from cavbench.errors import VersionConflict as VersionConflictError
from cavbench.scenarios.models import JSONValue
from cavbench.util import thaw


@dataclass(frozen=True)
class MutationResult:
    before: Mapping[str, JSONValue]
    after: Mapping[str, JSONValue]


class VersionedStateStore:
    def __init__(self, initial_state: Mapping[str, Mapping[str, Mapping[str, JSONValue]]]) -> None:
        # `initial_state` may hold immutable (MappingProxyType) containers
        # from the frozen scenario domain model; `thaw` rebuilds plain,
        # independently-mutable dicts rather than relying on `copy.deepcopy`,
        # which cannot pickle `mappingproxy` on some Python versions.
        self._resources: dict[tuple[str, str], dict[str, JSONValue]] = {}
        for namespace, bucket in initial_state.items():
            for resource_id, fields in bucket.items():
                self._resources[(namespace, str(resource_id))] = thaw(fields)

    def exists(self, namespace: str, resource_id: str) -> bool:
        return (namespace, str(resource_id)) in self._resources

    def get(self, namespace: str, resource_id: str) -> dict[str, JSONValue]:
        key = (namespace, str(resource_id))
        if key not in self._resources:
            raise ResourceNotFound(f"{namespace}:{resource_id}")
        return deepcopy(self._resources[key])

    def version(self, namespace: str, resource_id: str) -> int | None:
        return self.get(namespace, resource_id).get("version")

    def mutate(
        self,
        namespace: str,
        resource_id: str,
        changes: Mapping[str, JSONValue],
        *,
        expected_version: int | None = None,
    ) -> MutationResult:
        key = (namespace, str(resource_id))
        if key not in self._resources:
            raise ResourceNotFound(f"{namespace}:{resource_id}")
        resource = self._resources[key]
        before = deepcopy(resource)
        current_version = resource.get("version")
        if expected_version is not None and current_version != expected_version:
            raise VersionConflictError(
                f"Expected {namespace}:{resource_id} version {expected_version}, found {current_version}"
            )
        for path, value in changes.items():
            self._set_path(resource, path, thaw(value))
        if isinstance(current_version, int):
            resource["version"] = current_version + 1
        return MutationResult(before=before, after=deepcopy(resource))

    def snapshot(self) -> dict[str, dict[str, dict[str, JSONValue]]]:
        out: dict[str, dict[str, dict[str, JSONValue]]] = {}
        for (namespace, resource_id), fields in self._resources.items():
            out.setdefault(namespace, {})[resource_id] = deepcopy(fields)
        return out

    @staticmethod
    def _set_path(obj: dict[str, JSONValue], dotted_path: str, value: JSONValue) -> None:
        parts = dotted_path.split(".")
        cursor = obj
        for part in parts[:-1]:
            nxt = cursor.setdefault(part, {})
            if not isinstance(nxt, dict):
                raise ValueError(f"Cannot descend into non-object path segment: {part!r}")
            cursor = nxt
        cursor[parts[-1]] = value
