from pathlib import Path


def test_core_pipeline_does_not_import_observability():
    backend = Path(__file__).resolve().parents[2]
    app_dir = backend / "app"
    violations = []
    for path in app_dir.rglob("*.py"):
        if path.name == "main.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "observability" in text:
            violations.append(str(path.relative_to(backend)))
    assert violations == [], f"Core modules must not depend on observability: {violations}"


def test_only_main_mounts_observability_router():
    backend = Path(__file__).resolve().parents[2]
    main_text = (backend / "app" / "main.py").read_text(encoding="utf-8")
    assert "from observability.router import router as observability_router" in main_text
    assert "app.include_router(observability_router)" in main_text
