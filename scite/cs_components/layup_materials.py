"""
Layup materials — composition-based GWP and cost for floor-system layers.

A small, dictionary-backed material register for the layers of a floor layup
(structural concrete, FRP reinforcement, ballast / insulation fill, top plate).
Each material is described by its **composition** (constituents in kg per m³ of
material) and the embodied carbon of every constituent, so the GWP follows from
what the material is made of — e.g. how much cement a foam concrete needs —
instead of a single flat factor.

    GWP [kgCO₂e/m³] = Σ_i  m_i [kg/m³] · e_i [kgCO₂e/kg]        (A1–A3)

Status: plain Python dictionaries (``CONSTITUENTS``, ``LAYUP_MATERIALS``). The
records are shaped like the ``cs_components`` catalog so they can later be moved
into the catalog database (``catalog_manager``) and pulled from there; the
accessors ``get_layup_material`` / ``layup_materials`` are the stable interface.

**All values are indicative** orders of magnitude of generic (non product-specific)
cradle-to-gate data, for teaching and comparison — replace them with EPD data of
the intended products.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Category = Literal['concrete', 'fill', 'frp']


@dataclass(frozen=True)
class Constituent:
    """A raw material of a mix with its embodied carbon (A1–A3)."""

    key: str
    name: str
    gwp: float          # [kgCO₂e/kg]
    note: str = ''


# Indicative generic factors [kgCO₂e/kg] — orders of magnitude, not EPD values.
CONSTITUENTS: dict[str, Constituent] = {c.key: c for c in (
    Constituent('CEM I', 'Portland cement CEM I', 0.83),
    Constituent('CEM II/A', 'Portland-composite cement CEM II/A', 0.70),
    Constituent('CEM III/A', 'blast-furnace cement CEM III/A', 0.45),
    Constituent('CEM III/B', 'blast-furnace cement CEM III/B', 0.30),
    Constituent('fly ash', 'fly ash (by-product, allocated)', 0.01),
    Constituent('sand', 'sand 0/2', 0.005),
    Constituent('gravel', 'gravel / crushed aggregate', 0.004),
    Constituent('water', 'water', 0.0003),
    Constituent('superplasticizer', 'superplasticizer', 1.9),
    Constituent('foaming agent', 'foaming agent (synthetic / protein)', 1.5),
    Constituent('EPS beads', 'expanded polystyrene beads', 3.3),
    Constituent('expanded clay', 'expanded clay aggregate', 0.25),
    Constituent('foam glass gravel', 'foam glass gravel (recycled glass)', 0.15),
    Constituent('carbon fibre', 'carbon fibre (PAN-based)', 24.0),
    Constituent('epoxy resin', 'epoxy resin', 6.0),
)}


@dataclass(frozen=True)
class LayupMaterial:
    """A material of a floor layer: composition, LCA and mechanical data.

    Either ``composition`` [kg/m³ of material] (GWP from the constituents) or a
    flat ``gwp_flat`` [kgCO₂e/kg] (reference values) defines the embodied carbon.

    Mechanical fields are used for fills (FoamConcrete parameters); concretes take
    their strength from the structural model, FRP from the reinforcement fields.
    """

    key: str
    name: str
    category: Category
    rho: float                                  # [kg/m³] (dry density for fills)
    cost_m3: float                              # [EUR/m³]
    composition: dict = field(default_factory=dict)   # {constituent key: kg/m³}
    gwp_flat: float | None = None               # [kgCO₂e/kg] — overrides composition
    f_c: float | None = None                    # [MPa] fill compressive strength
    E: float | None = None                      # [MPa] fill modulus
    eps_cu: float | None = None                 # [-] fill limit strain (negative)
    structural: bool = True                     # False: mass only (loose fill)
    note: str = ''

    @property
    def gwp_m3(self) -> float:
        """Embodied carbon per m³ of material [kgCO₂e/m³]."""
        if self.gwp_flat is not None:
            return self.gwp_flat * self.rho
        return sum(m * CONSTITUENTS[c].gwp for c, m in self.composition.items())

    @property
    def gwp_kg(self) -> float:
        """Embodied carbon per kg of material [kgCO₂e/kg]."""
        return self.gwp_m3 / self.rho

    @property
    def cost_kg(self) -> float:
        """Cost per kg [EUR/kg]."""
        return self.cost_m3 / self.rho

    @property
    def binder(self) -> float:
        """Cement + supplementary binder content [kg/m³] (cement types, fly ash)."""
        return sum(m for c, m in self.composition.items()
                   if c.startswith('CEM') or c == 'fly ash')

    def breakdown(self) -> list[tuple[str, float, float, float]]:
        """[(constituent, kg/m³, kgCO₂e/kg, kgCO₂e/m³), ...] sorted by contribution."""
        rows = [(c, m, CONSTITUENTS[c].gwp, m * CONSTITUENTS[c].gwp)
                for c, m in self.composition.items()]
        return sorted(rows, key=lambda r: -r[3])

    def composition_text(self, max_items: int = 4) -> str:
        """Short composition string, e.g. 'CEM I 350 · sand 180 · water 175'."""
        if not self.composition:
            return f'flat {self.gwp_flat:g} kgCO₂e/kg' if self.gwp_flat is not None else '—'
        items = sorted(self.composition.items(), key=lambda kv: -kv[1])[:max_items]
        return ' · '.join(f'{c} {m:g}' for c, m in items)


def _mats(*records: LayupMaterial) -> dict[str, LayupMaterial]:
    return {m.key: m for m in records}


# Indicative mixes [kg/m³]. Foam concretes: dry density ≈ 1.2·cement + sand.
LAYUP_MATERIALS: dict[str, LayupMaterial] = _mats(
    # ── structural concrete ────────────────────────────────────────────────────
    LayupMaterial('icc reference (flat)', 'reference concrete, flat factor', 'concrete',
                  rho=2500.0, cost_m3=150.0, gwp_flat=0.17,
                  note='flat factor of all Chapter 1-3 models (comparability)'),
    LayupMaterial('C30/37 CEM I', 'normal concrete C30/37, CEM I', 'concrete',
                  rho=2312.0, cost_m3=150.0,
                  composition={'CEM I': 340, 'water': 170, 'sand': 760, 'gravel': 1040,
                               'superplasticizer': 2}),
    LayupMaterial('C30/37 CEM II/A', 'normal concrete C30/37, CEM II/A', 'concrete',
                  rho=2312.0, cost_m3=148.0,
                  composition={'CEM II/A': 340, 'water': 170, 'sand': 760, 'gravel': 1040,
                               'superplasticizer': 2}),
    LayupMaterial('C30/37 CEM III/A', 'normal concrete C30/37, CEM III/A', 'concrete',
                  rho=2312.0, cost_m3=148.0,
                  composition={'CEM III/A': 340, 'water': 170, 'sand': 760, 'gravel': 1040,
                               'superplasticizer': 2}),
    LayupMaterial('C25/30 CEM III/B', 'concrete / screed C25/30, CEM III/B', 'concrete',
                  rho=2265.0, cost_m3=140.0,
                  composition={'CEM III/B': 300, 'water': 165, 'sand': 800, 'gravel': 1000}),
    # ── ballast / insulation fill ──────────────────────────────────────────────
    LayupMaterial('FC400', 'foam concrete 400 kg/m³, CEM I', 'fill',
                  rho=400.0, cost_m3=115.0, f_c=1.0, E=500.0, eps_cu=-0.009,
                  composition={'CEM I': 330, 'water': 165, 'foaming agent': 1.0}),
    LayupMaterial('FC600', 'foam concrete 600 kg/m³, CEM I', 'fill',
                  rho=600.0, cost_m3=105.0, f_c=2.0, E=1250.0, eps_cu=-0.008,
                  composition={'CEM I': 350, 'sand': 180, 'water': 175, 'foaming agent': 0.8}),
    LayupMaterial('FC800', 'foam concrete 800 kg/m³, CEM I', 'fill',
                  rho=800.0, cost_m3=105.0, f_c=4.0, E=2500.0, eps_cu=-0.006,
                  composition={'CEM I': 360, 'sand': 370, 'water': 180, 'foaming agent': 0.6}),
    LayupMaterial('FC1000', 'foam concrete 1000 kg/m³, CEM I', 'fill',
                  rho=1000.0, cost_m3=115.0, f_c=7.0, E=4000.0, eps_cu=-0.005,
                  composition={'CEM I': 380, 'sand': 545, 'water': 190, 'foaming agent': 0.5}),
    LayupMaterial('FC600 CEM III/B', 'foam concrete 600 kg/m³, CEM III/B', 'fill',
                  rho=600.0, cost_m3=105.0, f_c=2.0, E=1250.0, eps_cu=-0.008,
                  composition={'CEM III/B': 350, 'sand': 180, 'water': 175,
                               'foaming agent': 0.8},
                  note='mechanical data assumed equal to FC600'),
    LayupMaterial('FC600 50% fly ash', 'foam concrete 600 kg/m³, 50 % fly ash', 'fill',
                  rho=600.0, cost_m3=100.0, f_c=2.0, E=1250.0, eps_cu=-0.008,
                  composition={'CEM I': 175, 'fly ash': 175, 'sand': 180, 'water': 175,
                               'foaming agent': 0.8},
                  note='mechanical data assumed equal to FC600'),
    LayupMaterial('EPS-bound fill', 'cement-bound EPS bead fill ~200 kg/m³', 'fill',
                  rho=200.0, cost_m3=90.0, f_c=0.4, E=40.0,
                  composition={'CEM I': 150, 'EPS beads': 12, 'water': 75}),
    LayupMaterial('expanded clay', 'expanded clay, loose fill', 'fill',
                  rho=350.0, cost_m3=80.0, structural=False,
                  composition={'expanded clay': 350}),
    LayupMaterial('glass-foam gravel', 'foam glass gravel, loose fill', 'fill',
                  rho=175.0, cost_m3=90.0, structural=False,
                  composition={'foam glass gravel': 175}),
    # ── FRP reinforcement ──────────────────────────────────────────────────────
    LayupMaterial('icc reference CFRP (flat)', 'CFRP, flat factor', 'frp',
                  rho=1600.0, cost_m3=160_000.0, gwp_flat=19.0,
                  note='flat factor of all Chapter 1-3 CRC models (comparability)'),
    LayupMaterial('CFRP grid C/epoxy', 'CFRP grid, carbon / epoxy 60:40 by mass', 'frp',
                  rho=1600.0, cost_m3=160_000.0,
                  composition={'carbon fibre': 960, 'epoxy resin': 640}),
)


def get_layup_material(key: str) -> LayupMaterial:
    """Material record by key (KeyError lists the available keys)."""
    try:
        return LAYUP_MATERIALS[key]
    except KeyError:
        raise KeyError(f'unknown layup material {key!r}; '
                       f'choose from {sorted(LAYUP_MATERIALS)}') from None


def layup_materials(category: Category) -> dict[str, LayupMaterial]:
    """All materials of one category, in register order."""
    return {k: m for k, m in LAYUP_MATERIALS.items() if m.category == category}
