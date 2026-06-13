"""
scite_app/registry.py — SCITE course navigation registry.

Defines the Part / Chapter / Model hierarchy for the SCITE teaching course.
"""
from __future__ import annotations

from pathlib import Path

from cframe import ChapterSpec, EducationalSpec, ModelEntry, PartSpec

from scite.scite_app.models.mkappa_model import MKappaInteractive

_CONTENT = Path(__file__).parent / "content"


def _edu(read_md: str, ex_md: str, ai_ctx: str) -> EducationalSpec:
    """Helper to create EducationalSpec with consistent paths."""
    return EducationalSpec(
        read_learn=str(_CONTENT / read_md),
        test_yourself=str(_CONTENT / ex_md),
        ai_context=ai_ctx,
    )


PARTS: list[PartSpec] = [
    PartSpec(
        label="Part I — Cross-Section Analysis",
        chapters=[
            ChapterSpec(
                key="ch1_mkappa",
                title="1-1  Moment-Curvature (M-κ) Analysis",
                models=[
                    ModelEntry(
                        key="mkappa_basic",
                        title="M-κ Basic Analysis",
                        node_cls=MKappaInteractive,
                    ),
                ],
                educational=EducationalSpec(
                    read_learn="",  # TODO: Add theory markdown
                    test_yourself="",  # TODO: Add exercises markdown
                    ai_context=(
                        "Moment-curvature (M-κ) analysis of reinforced concrete "
                        "cross-sections using EC2 parabola-rectangle stress block. "
                        "Explores the relationship between applied moment M and "
                        "curvature κ for various axial force levels N_Ed. "
                        "Predefined rectangular cross-section: 200×500mm, C30/35 concrete, "
                        "4×D16 reinforcement bars."
                    ),
                ),
                expanded=True,
            ),
        ],
    ),
    # TODO: Add more parts as course develops
    # PartSpec(
    #     label="Part II — Cross-Section Design",
    #     chapters=[...],
    # ),
]
