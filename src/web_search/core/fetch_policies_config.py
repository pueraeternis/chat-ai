"""Pydantic models for ``config/fetch_policies.yaml``."""

import ipaddress
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class FetchPoliciesConfig(BaseModel):
    """Declarative fetch policies loaded from YAML."""

    allowed_schemes: frozenset[str] = Field(
        ...,
        description="Lowercase URL schemes permitted for fetch tools.",
    )
    extra_blocked_cidrs: tuple[str, ...] = Field(
        default=(),
        description="Optional extra IPv4/IPv6 CIDR strings to reject.",
    )

    @field_validator("allowed_schemes", mode="before")
    @classmethod
    def _normalize_schemes(cls, value: object) -> frozenset[str]:
        if not isinstance(value, (list, tuple, frozenset, set)):
            msg = "allowed_schemes must be a list of strings"
            raise TypeError(msg)
        schemes = {str(s).strip().lower() for s in value}
        schemes.discard("")
        return frozenset(schemes)

    @property
    def extra_blocked_networks(self) -> tuple:
        nets: list = []
        for cidr in self.extra_blocked_cidrs:
            nets.append(ipaddress.ip_network(cidr, strict=False))
        return tuple(nets)


def load_fetch_policies_config(path: Path) -> FetchPoliciesConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"Fetch policies must be a mapping at root: {path}"
        raise TypeError(msg)
    return FetchPoliciesConfig.model_validate(raw)
