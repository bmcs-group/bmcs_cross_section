# State Management Strategy for SCITE Streamlit App

**Date:** January 12, 2026  
**Purpose:** Define consistent state management across workflow steps  
**Problem:** Cross-section changes weren't propagating to downstream views (NM Assessment)

---

## The Challenge

SCITE has a **sequential workflow**:

```
1. Components → 2. Cross-Section → 3. State Profiles → 4. M-κ Analysis → 5. NM Assessment → 6. Summary
```

**User Flow:**
1. User defines cross-section in **Step 2** (shape, concrete, reinforcement)
2. User proceeds to **Step 5** (NM Assessment) - view creates analysis objects
3. User goes BACK to **Step 2** and modifies reinforcement (adds/removes layers)
4. User returns to **Step 5**
5. **Problem:** Old reinforcement still displayed! ❌

**Root Cause:** Views create analysis objects once in `st.session_state` but don't detect when upstream cross-section changes.

---

## Solution: Hash-Based Change Detection

### Pattern Overview

```python
# 1. Generate hash of cross-section state
current_cs_hash = get_cross_section_hash(cs)

# 2. Compare with stored hash
if st.session_state.stored_hash != current_cs_hash:
    # Cross-section changed - recreate analysis object
    recreate_analysis()
    st.session_state.stored_hash = current_cs_hash
```

### Implementation

```python
def get_cross_section_hash(cs):
    """
    Generate MD5 hash of cross-section parameters.
    Changes in shape, concrete, or reinforcement → Different hash
    """
    import hashlib
    import json
    
    cs_data = {
        'shape': {
            'type': cs.shape.__class__.__name__,
            'b': cs.shape.b,
            'h': cs.shape.h if hasattr(cs.shape, 'h') else cs.shape.h_total,
        },
        'concrete': {
            'f_ck': cs.concrete.f_ck,
            'E_ct': cs.concrete.E_ct if hasattr(cs.concrete, 'E_ct') else None,
        },
        'layers': [
            {
                'z': layer.z,
                'A_s': layer.A_s,
                'material': {
                    'f_sy': layer.material.f_sy,
                    'E_s': layer.material.E_s,
                }
            }
            for layer in cs.reinforcement.layers
        ]
    }
    
    cs_json = json.dumps(cs_data, sort_keys=True)
    return hashlib.md5(cs_json.encode()).hexdigest()
```

---

## Workflow Step Patterns

### Step 2: Cross-Section Definition (Source of Truth)

**Role:** Define geometry, materials, reinforcement  
**State Keys:**
- `cs_shape_params` - Shape parameters (type, b, h, etc.)
- `cs_concrete_selected` - Concrete class (e.g., "C30/37")
- `cs_layers` - List of reinforcement layer definitions

**Behavior:**
- User modifies parameters
- Changes stored immediately in session state
- No hash tracking needed (source of truth)

---

### Step 3: State Profiles (Read-Only Visualization)

**Role:** Visualize strain/stress at specific states  
**Dependencies:** Cross-section from Step 2

**Pattern:**
```python
def render_state_profiles_view():
    # Always rebuild cross-section from current state
    cs = get_cross_section_from_state()
    
    # Create profile on demand (no caching)
    profile = StressStrainProfile(cs=cs, kappa=kappa, eps_bottom=eps_bot)
    profile.plot_stress_strain_profile(...)
```

**No State Management Needed:** Profiles are ephemeral visualizations, rebuilt every time.

---

### Step 4: M-κ Analysis (Computational - Requires Solve)

**Role:** Compute moment-curvature relationship  
**Dependencies:** Cross-section from Step 2  
**Challenge:** Expensive computation - don't recompute unless necessary

**Pattern:**
```python
def render_mkappa_analysis_view():
    cs = get_cross_section_from_state()
    
    # Check if cross-section changed
    current_cs_hash = get_cross_section_hash(cs)
    
    if 'mkappa_cs_hash' not in st.session_state:
        st.session_state.mkappa_cs_hash = None
    
    cs_changed = (st.session_state.mkappa_cs_hash != current_cs_hash)
    
    # Track what changed
    if cs_changed:
        st.session_state.cs_design_changed = True
    
    # Check solver parameter changes
    if solver_params_changed:
        st.session_state.mkappa_params_changed = True
    
    # Show status
    needs_recalc = (cs_changed or params_changed or not solved_yet)
    
    if needs_recalc:
        st.button("⚠️ Recalculate (Cross-Section Changed)")
    else:
        st.button("✓ Up to Date", disabled=True)
    
    # Solve on button click
    if solve_button:
        mkappa = MKappaAnalysis(cs=cs, ...)
        mkappa.solve()
        st.session_state.mkappa = mkappa
        st.session_state.mkappa_cs_hash = current_cs_hash
        st.session_state.cs_design_changed = False
```

**Key Principle:** Explicit user action (button click) to trigger expensive computation.

---

### Step 5: NM Assessment (Interactive - Real-Time)

**Role:** Explore equilibrium with manual strain control  
**Dependencies:** Cross-section from Step 2  
**Challenge:** Real-time updates as user adjusts sliders

**Pattern (FIXED):**
```python
def render_nm_assessment_view():
    cs = get_cross_section_from_state()
    
    # Check if cross-section changed
    current_cs_hash = get_cross_section_hash(cs)
    
    if 'nm_cs_hash' not in st.session_state:
        st.session_state.nm_cs_hash = None
    
    cs_changed = (st.session_state.nm_cs_hash != current_cs_hash)
    
    # Recreate NMAssessment if cross-section changed
    if 'nm_assessment' not in st.session_state or cs_changed:
        # Preserve user's load settings when recreating
        N_Ed = 0.0
        M_Ed = 200.0
        if 'nm_assessment' in st.session_state:
            N_Ed = st.session_state.nm_assessment.N_Ed
            M_Ed = st.session_state.nm_assessment.M_Ed
        
        st.session_state.nm_assessment = NMAssessment(
            cs=cs,
            eps_top=-0.0035,
            eps_bot=0.0025,
            N_Ed=N_Ed,
            M_Ed=M_Ed
        )
        st.session_state.nm_cs_hash = current_cs_hash
        
        if cs_changed:
            st.success("✓ Cross-section updated - NM Assessment refreshed")
    
    nm = st.session_state.nm_assessment
    
    # Real-time updates from sliders
    eps_s1 = st.slider("ε_s1", ...)
    nm.eps_bot = calculate_eps_bot(eps_s1, ...)  # Update state directly
    
    # Plot reflects current state immediately
    nm.profile.plot_stress_strain_profile(...)
```

**Key Principle:** Silent auto-refresh when cross-section changes, preserve user inputs.

---

### Step 6: Summary (Read-Only Report)

**Role:** Generate documentation from all steps  
**Dependencies:** All previous steps

**Pattern:**
```python
def render_summary_view():
    cs = get_cross_section_from_state()
    
    # Check if M-κ analysis exists
    if 'mkappa' in st.session_state:
        mkappa = st.session_state.mkappa
        # Check if outdated
        mkappa_hash = st.session_state.get('mkappa_cs_hash')
        current_hash = get_cross_section_hash(cs)
        
        if mkappa_hash != current_hash:
            st.warning("⚠️ M-κ analysis is outdated. Recalculate in Step 4.")
    
    # Generate report with current data
    generate_pdf_report(cs, mkappa, ...)
```

**Key Principle:** Show what exists, warn if outdated, don't auto-recompute.

---

## State Invalidation Rules

### Upstream Changes Invalidate Downstream

```
Cross-Section Modified
    ↓
    ├─ State Profiles: ✓ Auto-refresh (lightweight)
    ├─ M-κ Analysis: ⚠️ Mark outdated, require button click
    ├─ NM Assessment: ✓ Auto-refresh with preserved loads
    └─ Summary: ⚠️ Warn if analysis outdated
```

### Decision Matrix

| View | Cross-Section Changed | Behavior | Reason |
|------|----------------------|----------|---------|
| **State Profiles** | Always current | Rebuild on every render | Lightweight, pure visualization |
| **M-κ Analysis** | Mark outdated | Require button click | Expensive computation |
| **NM Assessment** | Auto-refresh | Recreate with preserved loads | Interactive exploration, cheap |
| **Summary** | Show warning | Don't auto-recompute | Report current + warn outdated |

---

## Implementation Checklist

### For Each Downstream View:

- [ ] Import `get_cross_section_hash()` function
- [ ] Store hash in session state (e.g., `{view}_cs_hash`)
- [ ] Detect changes: `cs_changed = (stored_hash != current_hash)`
- [ ] Handle change appropriately:
  - Lightweight view → Recreate object silently
  - Expensive computation → Show button with change indicator
  - Report view → Show warning
- [ ] Update hash after recreating: `st.session_state.{view}_cs_hash = current_hash`
- [ ] Preserve user inputs when recreating (loads, parameters, selections)

### Testing Protocol:

1. **Define cross-section** in Step 2
2. **Navigate to downstream view** (Step 3, 4, or 5)
3. **Go back** to Step 2
4. **Modify cross-section** (add/remove layer, change concrete, resize)
5. **Return to downstream view**
6. **Verify:** View shows updated cross-section, not old state ✓

---

## Code Locations

**Hash Function:**
- [mkappa_analysis_view.py](../bmcs_cross_section/streamlit_app/mkappa_analysis_view.py#L20-L56)
- [nm_assessment_view.py](../bmcs_cross_section/streamlit_app/nm_assessment_view.py#L20-L60)

**Usage Examples:**
- **M-κ Analysis:** Lines 195-213 (detect change, mark outdated, button prompt)
- **NM Assessment:** Lines 123-156 (detect change, silent refresh, preserve loads)

**Session State Keys:**
- `{view}_cs_hash` - Stored hash of cross-section
- `{view}_params_changed` - Solver parameters changed flag
- `cs_design_changed` - Cross-section design changed flag
- `matmod_changed` - Material model changed flag

---

## Benefits of This Pattern

✅ **Consistency:** Same hash-based detection across all views  
✅ **User-Friendly:** No manual refresh needed for interactive views  
✅ **Performance:** Expensive computations only on explicit user action  
✅ **Preservation:** User inputs (loads, parameters) preserved across updates  
✅ **Transparency:** Clear indicators when data is outdated  
✅ **Reliability:** Cross-section changes always propagate correctly

---

## Future Enhancements

### Potential Improvements:

1. **Dependency Graph:** Formal graph showing which session keys depend on others
2. **Auto-Invalidation:** Central function that invalidates all downstream states
3. **Version Tracking:** Track not just "changed" but "what changed" for smarter updates
4. **Undo/Redo:** Store history of cross-section hashes for navigation
5. **Persistent Storage:** Save/load workspace with proper version tracking

### For Now:

The hash-based pattern is **simple, effective, and sufficient** for current needs. Each view implements the pattern independently with minimal boilerplate (~10 lines).

---

## Summary

**Problem:** Cross-section changes in Step 2 didn't update downstream views  
**Solution:** Hash-based change detection with view-specific handling  
**Result:** Consistent state management across the workflow

**Key Insight:** Different views need different update strategies based on their computational cost and interactivity. Hash detection is the common foundation, but response varies.

---

**Related Files:**
- [mkappa_analysis_view.py](../bmcs_cross_section/streamlit_app/mkappa_analysis_view.py) - Pattern implemented
- [nm_assessment_view.py](../bmcs_cross_section/streamlit_app/nm_assessment_view.py) - Pattern implemented (fixed)
- [state_profiles_view.py](../bmcs_cross_section/streamlit_app/state_profiles_view.py) - No caching needed
- [summary_view.py](../bmcs_cross_section/streamlit_app/summary_view.py) - Show warnings for outdated data
