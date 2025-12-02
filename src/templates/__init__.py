"""
Prompt Templates Module

Securely loads prompt templates from YAML files to protect against prompt injection.
Templates are loaded at module import time and cached for performance.
"""

import os
from pathlib import Path
from typing import Any

import yaml

from src.observability.logger import get_logger

logger = get_logger(__name__, component="templates")

# Template directory path
TEMPLATES_DIR = Path(__file__).parent

# Cache for loaded templates
_template_cache: dict[str, dict[str, Any]] = {}


class TemplateLoadError(Exception):
    """Raised when a template fails to load."""
    pass


def _load_template_file(filename: str) -> dict[str, Any]:
    """
    Load a YAML template file securely.

    Args:
        filename: Name of the YAML file (e.g., 'orchestrator.yaml')

    Returns:
        Dictionary containing template data

    Raises:
        TemplateLoadError: If file cannot be loaded or parsed
    """
    filepath = TEMPLATES_DIR / filename

    if not filepath.exists():
        raise TemplateLoadError(f"Template file not found: {filepath}")

    # Security check: ensure file is within templates directory
    try:
        filepath.resolve().relative_to(TEMPLATES_DIR.resolve())
    except ValueError:
        raise TemplateLoadError(f"Template path traversal detected: {filename}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Use safe_load to prevent arbitrary code execution
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise TemplateLoadError(f"Template must be a YAML mapping: {filename}")

        logger.debug("Template loaded", filename=filename)
        return data

    except yaml.YAMLError as e:
        raise TemplateLoadError(f"Invalid YAML in {filename}: {e}")
    except IOError as e:
        raise TemplateLoadError(f"Cannot read {filename}: {e}")


def get_template(name: str) -> dict[str, Any]:
    """
    Get a template by name (cached).

    Args:
        name: Template name without extension (e.g., 'orchestrator')

    Returns:
        Template data dictionary
    """
    if name not in _template_cache:
        filename = f"{name}.yaml"
        _template_cache[name] = _load_template_file(filename)

    return _template_cache[name]


def get_prompt(template_name: str, prompt_key: str = "instruction") -> str:
    """
    Get a specific prompt from a template.

    Args:
        template_name: Name of the template (e.g., 'orchestrator')
        prompt_key: Key within the template (default: 'instruction')

    Returns:
        The prompt string

    Raises:
        TemplateLoadError: If template or key not found
    """
    template = get_template(template_name)

    if prompt_key not in template:
        raise TemplateLoadError(
            f"Key '{prompt_key}' not found in template '{template_name}'"
        )

    prompt = template[prompt_key]

    if not isinstance(prompt, str):
        raise TemplateLoadError(
            f"Prompt '{prompt_key}' in '{template_name}' must be a string"
        )

    return prompt


def reload_templates() -> None:
    """Clear template cache to force reload on next access."""
    _template_cache.clear()
    logger.info("Template cache cleared")


# Pre-load all templates at import time for validation
def _validate_templates() -> None:
    """Validate all template files on module load."""
    template_files = [
        'orchestrator.yaml',
        'rag_agent.yaml',
        'risk_agent.yaml',
        'compare_agent.yaml',
        'report_agent.yaml',
        'simple_agent.yaml',
    ]

    for filename in template_files:
        try:
            name = filename.replace('.yaml', '')
            get_template(name)
        except TemplateLoadError as e:
            logger.warning("Template validation failed", filename=filename, error=str(e))


# Validate on import (but don't fail - templates might not exist yet)
try:
    _validate_templates()
except Exception as e:
    logger.warning("Template pre-validation skipped", error=str(e))
