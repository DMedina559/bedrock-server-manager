"""Normalize legacy Minecraft manifests at the external data boundary."""

from typing import Literal

from pydantic import model_validator

from .data import ManifestRecord


class PackManifest(ManifestRecord):
    pack_type: Literal["data", "script", "resources"]

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        header = data.get("header")
        if not isinstance(header, dict):
            return data
        header = dict(header)
        version = header.get("version")
        if isinstance(version, str):
            parts = [int(part) for part in version.split(".")]
            header["version"] = (parts + [0, 0, 0])[:3]
        if not isinstance(header.get("name"), str) or not header["name"]:
            header["name"] = "Unknown Subpack Container"
        data["header"] = header
        modules = data.get("modules")
        if (
            not isinstance(modules, list)
            or not modules
            or not isinstance(modules[0], dict)
        ):
            return data
        module = modules[0]
        pack_type = module.get("type")
        if not pack_type:
            description = str(module.get("description", "")).lower()
            if "resources" in description:
                pack_type = "resources"
            elif "data" in description or "behavior" in description:
                pack_type = "data"
            elif data.get("subpacks"):
                pack_type = "resources"
        data["pack_type"] = (
            pack_type.lower() if isinstance(pack_type, str) else pack_type
        )
        if not isinstance(data.get("subpacks", []), list):
            data["subpacks"] = []
        return data
