"""Multicolor detection service for design analysis."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.db.models.enums import MulticolorSource, MulticolorStatus

logger = get_logger(__name__)

# Multicolor detection patterns (case-insensitive)
MULTICOLOR_PATTERNS = [
    re.compile(r"multi[- ]?colou?r", re.IGNORECASE),
    re.compile(r"\bMMU\b", re.IGNORECASE),
    re.compile(r"\bAMS\b", re.IGNORECASE),
    re.compile(r"\bIDEX\b", re.IGNORECASE),
    re.compile(r"dual[- ]?colou?r", re.IGNORECASE),
    re.compile(r"multi[- ]?material", re.IGNORECASE),
    re.compile(r"\d+\s*colou?rs?", re.IGNORECASE),  # e.g., "4 color", "5 colors"
]


class MulticolorDetector:
    """Detects multicolor designs using heuristics and 3MF analysis."""

    def detect_from_text(self, text: str) -> bool:
        """Detect multicolor from text (caption or filename).

        Args:
            text: The text to analyze.

        Returns:
            True if multicolor keywords are found.
        """
        if not text:
            return False

        for pattern in MULTICOLOR_PATTERNS:
            if pattern.search(text):
                logger.debug(
                    "multicolor_detected_text",
                    pattern=pattern.pattern,
                    text=text[:100],
                )
                return True

        return False

    def detect_from_caption_and_files(
        self,
        caption: str | None,
        filenames: list[str],
    ) -> bool:
        """Detect multicolor from caption and filenames.

        Args:
            caption: Message caption text.
            filenames: List of attachment filenames.

        Returns:
            True if any source indicates multicolor.
        """
        # Check caption
        if caption and self.detect_from_text(caption):
            return True

        # Check filenames
        for filename in filenames:
            if self.detect_from_text(filename):
                return True

        return False

    def detect_from_3mf(self, threemf_path: Path) -> tuple[bool, dict[str, Any]]:
        """Detect multicolor from 3MF file structure.

        Analyzes the 3MF XML to find multiple materials/colors.

        Args:
            threemf_path: Path to the 3MF file.

        Returns:
            Tuple of (is_multicolor, details_dict).
        """
        details: dict[str, Any] = {
            "colors": [],
            "materials": [],
            "color_count": 0,
        }

        try:
            with zipfile.ZipFile(threemf_path, "r") as zf:
                # Find the model file
                model_path = self._find_model_file(zf)
                if not model_path:
                    return False, details

                # Parse the XML
                xml_content = zf.read(model_path)
                root = ET.fromstring(xml_content)

                # Find namespaces
                namespaces = self._extract_namespaces(root)

                # Look for basematerials
                colors = self._find_colors(root, namespaces)
                details["colors"] = colors
                details["color_count"] = len(colors)

                # Look for material references
                materials = self._find_materials(root, namespaces)
                details["materials"] = materials

                # Multicolor if more than one color/material
                is_multicolor = len(colors) > 1 or len(materials) > 1

                if is_multicolor:
                    logger.info(
                        "multicolor_detected_3mf",
                        file=str(threemf_path),
                        color_count=len(colors),
                        material_count=len(materials),
                    )

                return is_multicolor, details

        except (zipfile.BadZipFile, ET.ParseError, Exception) as e:
            logger.warning(
                "3mf_analysis_failed",
                file=str(threemf_path),
                error=str(e),
            )
            return False, details

    def _find_model_file(self, zf: zipfile.ZipFile) -> str | None:
        """Find the 3D model XML file in the 3MF archive."""
        # Common locations for model file
        candidates = [
            "3D/3dmodel.model",
            "3dmodel.model",
            "Metadata/model.model",
        ]

        namelist = zf.namelist()
        for candidate in candidates:
            if candidate in namelist:
                return candidate

        # Fall back to any .model file
        for name in namelist:
            if name.endswith(".model"):
                return name

        return None

    def _extract_namespaces(self, root: ET.Element) -> dict[str, str]:
        """Extract XML namespaces from root element."""
        namespaces = {}

        # Parse namespaces from tag
        if root.tag.startswith("{"):
            ns = root.tag[1:].split("}")[0]
            namespaces["default"] = ns

        # Check for common 3MF namespaces in attributes
        for attr, value in root.attrib.items():
            if attr.startswith("{"):
                ns_prefix = attr.split("}")[-1]
                ns_uri = attr[1:].split("}")[0]
                namespaces[ns_prefix] = ns_uri

        return namespaces

    def _find_colors(
        self,
        root: ET.Element,
        namespaces: dict[str, str],
    ) -> list[str]:
        """Find color definitions in the 3MF model."""
        colors = []

        # Search for basematerials/base elements with color attribute
        for elem in root.iter():
            tag_local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag_local.lower() == "base":
                color = elem.get("color")
                if color:
                    colors.append(color)

            # Also check for m:color or material color elements
            if tag_local.lower() == "color":
                color_value = elem.text or elem.get("value")
                if color_value:
                    colors.append(color_value)

        return list(set(colors))  # Dedupe

    def _find_materials(
        self,
        root: ET.Element,
        namespaces: dict[str, str],
    ) -> list[str]:
        """Find material references in the 3MF model."""
        materials = []

        # Look for objects with materialid or component materialids
        for elem in root.iter():
            tag_local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag_local.lower() in ("object", "component"):
                material_id = elem.get("materialid") or elem.get("pid")
                if material_id:
                    materials.append(material_id)

            # Look for basematerials containers
            if tag_local.lower() == "basematerials":
                mat_id = elem.get("id")
                if mat_id:
                    materials.append(f"basematerials_{mat_id}")

        return list(set(materials))  # Dedupe


# Singleton instance
_detector: MulticolorDetector | None = None


def get_multicolor_detector() -> MulticolorDetector:
    """Get the multicolor detector singleton."""
    global _detector
    if _detector is None:
        _detector = MulticolorDetector()
    return _detector
