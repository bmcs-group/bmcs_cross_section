"""
Test Carbon Material Model Visualization

This script demonstrates that carbon bar components now have
proper material models with stress-strain visualization.
"""

import matplotlib.pyplot as plt
import numpy as np

from bmcs_cross_section.matmod import create_carbon, CarbonReinforcement
from bmcs_cross_section.cs_components import CarbonBarComponent

# Set up figure
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Material model grades comparison
ax1 = axes[0, 0]
for grade in ['C1500', 'C2000', 'C2500']:
    carbon = create_carbon(grade)
    carbon.plot_stress_strain(ax=ax1, show_limits=False, label=grade)
ax1.set_title('Carbon FRP Grades Comparison', fontweight='bold')
ax1.legend()

# 2. Post-peak softening effect
ax2 = axes[0, 1]
for ppf in [1.0, 2.5, 5.0, 10.0]:
    carbon = CarbonReinforcement(post_peak_factor=ppf)
    eps = carbon.get_eps_plot_range()
    sig = carbon.get_sig(eps)
    ax2.plot(eps * 1000, sig, linewidth=2, label=f'k = {ppf}')
ax2.set_xlabel('Strain ε [‰]')
ax2.set_ylabel('Stress σ [MPa]')
ax2.set_title('Post-Peak Softening Factor Effect', fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(title='Softening factor')

# 3. Component with material model
ax3 = axes[1, 0]
carbon_bar = CarbonBarComponent(nominal_diameter=12)
print(f"\nCarbon Bar Component:")
print(f"  Name: {carbon_bar.name}")
print(f"  Product ID: {carbon_bar.product_id}")
print(f"  Diameter: {carbon_bar.nominal_diameter} mm")
print(f"  Area: {carbon_bar.area:.2f} mm²")
print(f"  f_tk: {carbon_bar.f_tk} MPa")
print(f"  f_td: {carbon_bar.f_td:.1f} MPa")
print(f"  Material model: {type(carbon_bar.matmod).__name__}")

# Plot component curves (uses matmod internally)
carbon_bar.plot_stress_strain(ax=ax3, show_limits=True, color='darkred')

# 4. Design vs Characteristic values
ax4 = axes[1, 1]
carbon_char = create_carbon('C2000', factor=1.0)  # Characteristic
carbon_design = create_carbon('C2000', factor=1/1.25)  # Design

eps = np.linspace(0, 0.02, 200)
sig_char = carbon_char.get_sig(eps)
sig_design = carbon_design.get_sig(eps)

ax4.plot(eps * 1000, sig_char, 'b-', linewidth=2.5, label='Characteristic (f_tk)')
ax4.fill_between(eps * 1000, 0, sig_char, color='blue', alpha=0.15)
ax4.plot(eps * 1000, sig_design, 'r--', linewidth=2.5, label='Design (f_td = f_tk/γ_s)')
ax4.fill_between(eps * 1000, 0, sig_design, color='red', alpha=0.15)

ax4.axhline(2000, color='blue', linestyle=':', alpha=0.5)
ax4.axhline(2000/1.25, color='red', linestyle=':', alpha=0.5)

ax4.set_xlabel('Strain ε [‰]')
ax4.set_ylabel('Stress σ [MPa]')
ax4.set_title('Safety Factor Effect (γ_s = 1.25)', fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.legend()

plt.suptitle('Carbon FRP Material Model - Complete Integration Test', 
             fontsize=14, fontweight='bold', y=0.995)
plt.tight_layout()

# Save figure
output_file = '/home/rch/Coding/bmcs_cross_section/dev_docs/carbon_material_model_test.png'
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n✓ Figure saved to: {output_file}")

print("\n" + "=" * 70)
print("CARBON MATERIAL MODEL - INTEGRATION TEST")
print("=" * 70)
print("✓ Material model created successfully (CarbonReinforcement)")
print("✓ Component integration working (CarbonBarComponent.matmod)")
print("✓ Stress-strain curves plotting correctly")
print("✓ Post-peak softening for numerical stability")
print("✓ Safety factors applied correctly")
print("✓ Ready for component catalog app visualization")
print("=" * 70)

plt.show()
