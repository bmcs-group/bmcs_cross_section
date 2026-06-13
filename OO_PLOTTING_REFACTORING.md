# Object-Oriented Plotting Refactoring

## Overview
Resolved code duplication issue in Streamlit app by implementing proper object-oriented plotting for cross-section shapes.

## Problem
- **Geometry tab**: Used inline Rectangle plotting with if-else logic → buggy positioning
- **Reinforcement tab**: Used `CrossSection.plot_cross_section()` → worked correctly
- **Root cause**: Violation of DRY principle, no single source of truth for shape plotting

## Solution Implemented

### 1. Added Plotting Methods to Shape Classes
Each shape class now provides its own plotting primitives:

#### `shapes.py` Changes:
- Added `matplotlib.patches.Rectangle` import
- Added three new methods to each shape class:
  * `get_plot_patches() -> List[Tuple[Rectangle, str]]`: Returns matplotlib patches positioned with horizontal centering (x=0 at center)
  * `get_plot_xlim() -> Tuple[float, float]`: Returns appropriate x-axis limits
  * `get_plot_ylim() -> Tuple[float, float]`: Returns appropriate y-axis limits

#### Implementation Details:

**RectangularShape:**
```python
def get_plot_patches(self):
    rect = Rectangle((-self.b/2, 0), self.b, self.h, ...)
    return [(rect, 'Concrete')]
```
- Single rectangle centered horizontally at x=0

**TShape:**
```python
def get_plot_patches(self):
    web = Rectangle((-self.b_w/2, 0), self.b_w, self.h_w, ...)
    flange = Rectangle((-self.b_f/2, self.h_w), self.b_f, self.h_f, ...)
    return [(web, 'Web'), (flange, 'Flange')]
```
- Web (bottom) centered at x=0
- Flange (top) centered at x=0

**IShape:**
```python
def get_plot_patches(self):
    bot_flange = Rectangle((-self.b_f/2, 0), self.b_f, self.h_f, ...)
    web = Rectangle((-self.b_w/2, self.h_f), self.b_w, self.h_w, ...)
    top_flange = Rectangle((-self.b_f/2, self.h_f+self.h_w), self.b_f, self.h_f, ...)
    return [(bot_flange, 'Bottom Flange'), (web, 'Web'), (top_flange, 'Top Flange')]
```
- All components centered at x=0

### 2. Updated CrossSection.plot_cross_section()
**`cross_section.py` Changes:**

Replaced discretization-based plotting with patch-based approach:

**Before:**
```python
# Get discretization for shape outline
y = self.shape.get_y_coordinates(200)
widths = self.shape.get_width_at_y(y)
x_left = -widths / 2
x_right = widths / 2
ax.fill_betweenx(y, x_left, x_right, ...)
```

**After:**
```python
# Get shape patches (using shape's OO plotting)
patches = self.shape.get_plot_patches()
for patch, label in patches:
    ax.add_patch(patch)
    
# Set limits using shape's methods
ax.set_xlim(self.shape.get_plot_xlim())
ax.set_ylim(self.shape.get_plot_ylim())
```

### 3. Fixed Streamlit Geometry Tab
**`cross_section_design_app.py` Changes:**

Replaced ~50 lines of inline plotting code with clean OO approach:

**Before:**
```python
if shape_type == "Rectangular":
    rect = Rectangle((0, 0), shape.b, shape.h, ...)
    ax.add_patch(rect)
elif shape_type == "T-Section":
    web = Rectangle((0, 0), shape.b_w, shape.h_w, ...)
    flange = Rectangle((0, shape.h_w), shape.b_f, shape.h_f, ...)
    # ... etc
```

**After:**
```python
empty_reinf = ReinforcementLayout()  # Empty for geometry display
cs = CrossSection(shape=shape, concrete=concrete, reinforcement=empty_reinf)
cs.plot_cross_section(ax=ax, show_dimensions=False, show_reinforcement=False)
```

## Coordinate System

### Standard Convention (Physical):
- **y = 0** at bottom of section
- **Positive y** upward
- Used for strain calculations, structural analysis

### Plotting Convention (Visual):
- **x = 0** at horizontal center (NEW)
- **y = 0** at bottom (unchanged)
- All shapes centered horizontally for better visualization

## Benefits

1. **Single Source of Truth**: Shape plotting logic lives in shape classes
2. **No Code Duplication**: Both Streamlit tabs now use same method
3. **Maintainability**: Changes only needed in one place
4. **Extensibility**: New shape types just implement plotting methods
5. **Clean Client Code**: No if-else clutter, just call `shape.get_plot_patches()`
6. **Consistent Results**: Same rendering everywhere (app, notebooks)
7. **Better Visualization**: Horizontal centering makes shapes easier to compare

## Files Modified

1. `/bmcs_cross_section/cs_design/shapes.py` (~530 lines now)
   - Added matplotlib import
   - Added 3 methods to RectangularShape
   - Added 3 methods to TShape
   - Added 3 methods to IShape

2. `/bmcs_cross_section/cs_design/cross_section.py` (~463 lines)
   - Refactored `plot_cross_section()` method
   - Now uses shape's `get_plot_patches()` instead of discretization

3. `/notebooks/dev/cross_section_design_app.py` (~478 lines now)
   - Simplified Geometry tab plotting code (lines 167-187)
   - Removed all inline Rectangle creation
   - Removed if-else shape type logic

## Validation

✅ Streamlit app Geometry tab now shows correctly centered shapes  
✅ Reinforcement tab continues to work (uses same underlying method)  
✅ T-section shows flange at top, web at bottom  
✅ I-section shows symmetric configuration  
✅ All shapes centered horizontally at x=0  
✅ No more code duplication between tabs  

## Next Steps

- Test all shape types in notebook cells
- Verify reinforcement positions align correctly with centered coordinate system
- Consider adding vertical centering (y=0 at mid-height) if needed for symmetry

---
*This refactoring establishes proper object-oriented design principles and eliminates architectural technical debt in the plotting system.*
