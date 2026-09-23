"""Phase 1 — resource/ layout và default paths."""

from pathlib import Path

from src.config import get_settings
from src.db.catalog import get_catalog
from src.prompts.registry import registry


def test_resource_dirs_exist():
    root = Path(__file__).resolve().parent.parent
    assert (root / "resource" / "prompts").is_dir()
    assert (root / "resource" / "docs" / "vms_yaml" / "index.yaml").is_file()
    assert (root / "resource" / "db" / "catalog.yaml").is_file()


def test_default_docs_root_and_prompts_dir():
    settings = get_settings()
    assert settings.docs_root == "resource/docs/vms_yaml"
    assert (settings.effective_docs_root / "index.yaml").exists()

    reg = registry()
    assert reg.prompts_dir.name == "prompts"
    assert reg.prompts_dir.parent.name == "resource"
    assert (reg.prompts_dir / "sql_agent" / "production.txt").exists()


def test_catalog_loads_from_yaml():
    catalog = get_catalog()
    assert "plate_event" in catalog
    assert "fire_smoke_event" in catalog
