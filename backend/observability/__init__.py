"""Read-only observability plugin.

This package is deliberately outside ``app`` so visualization and human-readable
logs cannot become workflow dependencies.  It only reads persisted workflow
state/agent runs; the core pipeline never imports from this package.
"""
