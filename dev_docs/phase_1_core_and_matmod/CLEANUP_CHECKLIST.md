# Repository Cleanup Checklist

**Goal**: Remove all code not directly supporting mkappa to create a clean, focused codebase.

## ✅ Safe to Delete

These packages are not needed for mkappa:

### 1. MXN Package (M-N Interaction Diagrams)
```bash
git rm -r bmcs_cross_section/mxn/
```
**Reason**: Different application (interaction diagrams). Will re-add from main branch in Phase 4.

### 2. Pullout Package
```bash
git rm -r bmcs_cross_section/pullout/
```
**Reason**: Different application (pullout tests). Will re-add from main branch in Phase 5.

### 3. Crack Bridge Package
```bash
git rm -r bmcs_cross_section/crack_bridge/
```
**Reason**: Not used by mkappa currently.

### 4. Analytical Solutions (if standalone)
```bash
# Check if used by mkappa first
git rm -r bmcs_cross_section/analytical_solutions/
```
**Reason**: May contain useful symbolic derivations, but mkappa has its own.

### 5. Temporary Notebooks
```bash
git rm -r notebooks/temp/
git rm -r notebooks/wb_tessellation/
git rm notebooks/Chu19_*.ipynb
```
**Reason**: Temporary or unrelated research notebooks.

## ⚠️ Review Before Deleting

These might have useful content - check first:

### 1. Old Material Models
```
bmcs_cross_section/matmod/
├── concrete_old.py        # May have useful implementations
├── sz_advanced.py         # Advanced shear zone - check if needed
```
**Action**: Review for useful code, then delete if not needed for mkappa.

### 2. UML Diagrams
```
bmcs_cross_section/uml/
```
**Action**: Keep for reference, or move to dev_docs.

### 3. Deprecated CS Layouts
```
bmcs_cross_section/cs_design/
├── cs_layout.py           # List-based layout
├── cs_layout_dict.py      # Dict-based layout
```
**Action**: Choose one approach (dict is more flexible), delete the other.

## ✅ Must Keep

These are essential for mkappa:

### Core Packages
- ✅ `bmcs_cross_section/matmod/` - Material models (will refactor)
- ✅ `bmcs_cross_section/cs_design/` - Cross-section design (will refactor)
- ✅ `bmcs_cross_section/mkappa/` - Moment-curvature (will refactor)
- ✅ `bmcs_cross_section/norms/` - Design codes (EC2, ACI) - useful utilities

### Notebooks
- ✅ `notebooks/mkappa/` - Keep all, will update to new API

### Configuration
- ✅ `.vscode/settings.json`
- ✅ `pyproject.toml`
- ✅ `environment.yml`
- ✅ `README.md`
- ✅ `setup.py` (keep for now)

## Cleanup Script

Execute in order:

```bash
#!/bin/bash
# Run from repository root

# 1. Delete clearly unused packages
echo "Removing unused packages..."
git rm -r bmcs_cross_section/mxn/
git rm -r bmcs_cross_section/pullout/
git rm -r bmcs_cross_section/crack_bridge/

# 2. Delete temporary notebooks
echo "Removing temporary notebooks..."
git rm -r notebooks/temp/
git rm -r notebooks/wb_tessellation/ 

# 3. Delete old research notebooks
echo "Removing old research notebooks..."
git rm notebooks/Chu19_*.ipynb

# 4. Commit cleanup
echo "Committing cleanup..."
git add -A
git commit -m "refactor: remove packages not supporting mkappa

- Remove mxn package (interaction diagrams - Phase 4)
- Remove pullout package (pullout tests - Phase 5)
- Remove crack_bridge package (not used)
- Remove temporary and research notebooks
- Legacy code preserved on main branch"

echo "Cleanup complete!"
echo "Repository now focused on mkappa development."
```

## After Cleanup

Expected structure:

```
bmcs_cross_section/
├── .vscode/
│   └── settings.json
├── bmcs_cross_section/
│   ├── __init__.py
│   ├── api.py
│   ├── version.py
│   ├── matmod/              # To refactor
│   ├── cs_design/           # To refactor
│   ├── mkappa/              # To refactor
│   └── norms/               # Keep as is
├── dev_docs/                # Our documentation
├── notebooks/
│   └── mkappa/              # Keep and update
├── tests/                   # Will create
├── pyproject.toml
├── environment.yml
└── README.md
```

## Verification

After cleanup, verify:

```bash
# 1. Check what's left
ls -la bmcs_cross_section/

# 2. Run tests (if any exist)
pytest tests/ || echo "No tests yet"

# 3. Check imports still work
python -c "import bmcs_cross_section; print('OK')"

# 4. Check git status
git status
```

## Rollback Plan

If something breaks:

```bash
# Undo last commit
git reset --soft HEAD~1

# Or checkout specific files
git checkout main -- path/to/file
```

## Phase-Specific Cleanup

### After Phase 1 (Core + MatMod)
- [ ] Delete old material model implementations
- [ ] Clean up matmod directory structure

### After Phase 2 (MKappa)
- [ ] Delete old mkappa implementation
- [ ] Consolidate notebooks

### After Phase 3 (CS Design)
- [ ] Delete old cs_design implementation
- [ ] Final cleanup

## Size Reduction Estimate

Current repository size: ~XXX MB  
After cleanup: ~XXX MB  
Reduction: ~XX%

## Next Steps

1. [ ] Review this checklist with fresh eyes
2. [ ] Back up current state (already on main branch)
3. [ ] Execute cleanup script
4. [ ] Verify functionality
5. [ ] Start Phase 1 implementation

---

**Remember**: All deleted code is safe on the main branch. We can always cherry-pick useful code later.
