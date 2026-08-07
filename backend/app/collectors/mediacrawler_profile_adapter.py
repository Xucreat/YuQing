"""Translate application profiles into native MediaCrawler profile paths."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.collectors.mediacrawler_platform import (
    MediaCrawlerConfigurationError,
    MediaCrawlerPlatformSpec,
)


_PATH_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class MediaCrawlerProfileAdapterError(RuntimeError):
    """Raised when a native profile view cannot be prepared safely."""


@dataclass(frozen=True)
class MediaCrawlerProfileBinding:
    """One application profile and the native path visible to the crawler."""

    application_profile: Path
    upstream_root: Path
    upstream_profile: Path
    checkout_root: Path
    uses_native_view: bool

    @property
    def native_root(self) -> Path:
        """Compatibility/readability alias for the generated native profile root."""

        return self.upstream_root


class MediaCrawlerProfileAdapter:
    """Materialize a native profile view without changing business config.

    Upstream MediaCrawler resolves browser state relative to its working
    directory. A spec can therefore declare native relative profile parts,
    while this generic adapter supplies an isolated working directory and
    copies the application profile into that contract. A missing declaration
    is an identity mapping, which preserves the legacy Weibo policy.
    """

    def __init__(
        self,
        *,
        runtime_root: str | Path,
        platform_spec: MediaCrawlerPlatformSpec,
        source_key: str,
        trigger_type: str,
        checkout_root: str | Path | None = None,
        command_cwd: str | Path | None = None,
    ) -> None:
        if not source_key:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerProfileAdapter requires an explicit source_key"
            )
        self.runtime_root = Path(runtime_root).resolve()
        self.platform_spec = platform_spec
        self.source_key = self._validate_part(source_key, "source_key")
        self.trigger_type = self._validate_part(trigger_type, "trigger_type")
        # ``command_cwd`` is retained as a compatibility alias for older
        # callers. It no longer controls the subprocess cwd; checkout_root
        # does, while the generated native profile remains separate.
        self.checkout_root = Path(
            checkout_root or command_cwd or runtime_root
        ).resolve()

    @staticmethod
    def _validate_part(value: str, label: str) -> str:
        normalized = str(value).strip()
        if _PATH_PART_RE.fullmatch(normalized) is None:
            raise MediaCrawlerProfileAdapterError(f"invalid profile {label}")
        return normalized

    def _native_parts(self, platform_spec: MediaCrawlerPlatformSpec) -> tuple[str, ...]:
        parts = tuple(str(part).strip() for part in platform_spec.upstream_profile_parts)
        if any(_PATH_PART_RE.fullmatch(part) is None for part in parts):
            raise MediaCrawlerProfileAdapterError(
                f"invalid upstream profile parts for {platform_spec.platform}"
            )
        return parts

    def resolve_upstream_profile(
        self,
        platform_spec: MediaCrawlerPlatformSpec,
        application_profile: str | Path,
    ) -> MediaCrawlerProfileBinding:
        """Resolve the native path for one isolated application profile."""

        if platform_spec.platform != self.platform_spec.platform:
            raise MediaCrawlerConfigurationError(
                "profile adapter PlatformSpec does not match runtime PlatformSpec"
            )
        application = Path(application_profile).resolve()
        parts = self._native_parts(platform_spec)
        if not parts:
            return MediaCrawlerProfileBinding(
                application_profile=application,
                upstream_root=self.checkout_root,
                upstream_profile=application,
                checkout_root=self.checkout_root,
                uses_native_view=False,
            )

        native_root = (
            self.runtime_root
            / "upstream_profiles"
            / self._validate_part(platform_spec.platform, "platform")
            / self.source_key
            / self.trigger_type
        )
        return MediaCrawlerProfileBinding(
            application_profile=application,
            upstream_root=native_root,
            upstream_profile=native_root.joinpath(*parts),
            checkout_root=self.checkout_root,
            uses_native_view=True,
        )

    def prepare(
        self,
        platform_spec: MediaCrawlerPlatformSpec,
        application_profile: str | Path,
    ) -> MediaCrawlerProfileBinding:
        """Create the native profile view, retaining it until success cleanup."""

        binding = self.resolve_upstream_profile(platform_spec, application_profile)
        if not binding.uses_native_view:
            return binding
        if not binding.application_profile.is_dir():
            raise MediaCrawlerProfileAdapterError(
                f"application profile unavailable: {binding.application_profile}"
            )

        binding.upstream_root.mkdir(parents=True, exist_ok=True)
        if binding.upstream_profile.exists():
            if not binding.upstream_profile.is_dir():
                raise MediaCrawlerProfileAdapterError(
                    f"native profile path is not a directory: {binding.upstream_profile}"
                )
            return binding
        try:
            binding.upstream_profile.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                binding.application_profile,
                binding.upstream_profile,
                copy_function=shutil.copy2,
                dirs_exist_ok=False,
            )
        except Exception as exc:
            if binding.upstream_profile.exists():
                shutil.rmtree(binding.upstream_profile, ignore_errors=True)
            raise MediaCrawlerProfileAdapterError(
                f"unable to prepare native profile: {binding.upstream_profile}"
            ) from exc
        return binding

    def cleanup(self, binding: MediaCrawlerProfileBinding) -> None:
        """Remove only the generated native view after pipeline success."""

        if not binding.uses_native_view:
            return
        native_root = (self.runtime_root / "upstream_profiles").resolve()
        target = binding.upstream_root.resolve()
        if target == native_root or native_root not in target.parents:
            raise MediaCrawlerProfileAdapterError(
                f"refusing to remove native profile outside adapter root: {target}"
            )
        if target.exists():
            shutil.rmtree(target)


__all__ = [
    "MediaCrawlerProfileAdapter",
    "MediaCrawlerProfileAdapterError",
    "MediaCrawlerProfileBinding",
]
