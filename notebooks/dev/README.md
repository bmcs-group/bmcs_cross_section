# Development Notebooks

This folder contains **temporary development and testing notebooks** for the refactoring process.

## Purpose

These notebooks are for:
- Testing new core module functionality
- Prototyping material models
- Validating against legacy implementations
- Interactive development and debugging

## Structure

```
dev/
├── 00_test_core_module.ipynb          # Test core functionality
├── 01_test_ui_adapters.ipynb          # Test Jupyter/Streamlit UI
├── 02_prototype_ec2_concrete.ipynb    # Prototype EC2 concrete
├── 03_validation_ec2_concrete.ipynb   # Validate vs legacy
└── README.md                          # This file
```

## Lifecycle

**These are TEMPORARY notebooks:**
- Use during development
- Delete or move to archive when phase complete
- Keep only polished examples in `notebooks/mkappa/`

## Guidelines

1. **Name with numbers**: `00_`, `01_`, etc. for ordering
2. **Keep focused**: One topic per notebook
3. **Clean up**: Remove when done or move successful examples to main notebooks
4. **Don't commit junk**: Only commit working, documented notebooks

## Difference from `notebooks/mkappa/`

- `notebooks/mkappa/` → **Polished examples for users**
- `notebooks/dev/` → **Scratch space for developers**

## When to Graduate

Move notebooks from `dev/` to `mkappa/` when:
- ✅ Code is stable and tested
- ✅ Well documented with explanations
- ✅ Demonstrates a complete use case
- ✅ Ready for teaching or user reference

## Cleanup

At end of each phase:
```bash
# Review what's in dev/
ls notebooks/dev/

# Move useful ones
mv notebooks/dev/03_validation_ec2_concrete.ipynb notebooks/mkappa/validation/

# Delete temporary ones
rm notebooks/dev/00_test_*.ipynb
```

---

**Remember**: This is YOUR scratch space. Experiment freely!
