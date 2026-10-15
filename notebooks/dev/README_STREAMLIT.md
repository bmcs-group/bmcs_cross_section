# EC2 Concrete Model - Streamlit Web Application

## Quick Start

### 1. Install Streamlit (if not already installed)

```bash
conda activate icc_env
pip install streamlit
```

### 2. Run the Application

From the project root:

```bash
cd notebooks/dev
streamlit run ec2_concrete_streamlit_app.py
```

Or directly:

```bash
streamlit run notebooks/dev/ec2_concrete_streamlit_app.py
```

### 3. Open in Browser

The app will automatically open in your browser at:
- **Local URL**: http://localhost:8501
- **Network URL**: Will be displayed in terminal

## Features

### Interactive Controls (Sidebar)
- **f_cm**: Compressive strength (20-100 MPa)
- **μ (mu)**: Fiber reinforcement effect (0.0-1.0)
- **factor**: Stress scaling factor (0.5-1.5)

### Visualizations
1. **Main Stress-Strain Curve**: Full EC2 constitutive model
2. **Compression Branch**: Parabolic-rectangular behavior
3. **Tension Branch**: Fiber reinforcement effects
4. **Tangent Modulus**: Material stiffness evolution

### Model Information
- Automatic concrete grade estimation (C20/25 to C90/105)
- Derived properties (f_ck, E_cm, f_ctm)
- EC2 parameters (k, n, ε_c1, ε_cu1)
- Real-time updates on parameter changes

## Architecture

The application demonstrates the modern BMCS architecture:

```python
EC2Concrete (BMCSModel)
├── Pydantic validation
├── Cached properties
├── Symbolic expressions (SymPy)
└── UI adapters
    ├── Jupyter (ipywidgets)
    └── Streamlit (web interface)
```

## Comparison: Jupyter vs Streamlit

| Feature | Jupyter Notebook | Streamlit Web App |
|---------|------------------|-------------------|
| **Environment** | Local notebook | Web browser |
| **Widgets** | ipywidgets | Streamlit components |
| **Sharing** | .ipynb file | URL / deployment |
| **Interactivity** | In-cell | Full page layout |
| **Best for** | Development, testing | Demos, end-users |

## Tips

### Performance
- Streamlit reruns the entire script on parameter change
- Model caching helps performance
- For production, consider using `@st.cache_data` decorator

### Customization
Edit `ec2_concrete_streamlit_app.py` to:
- Change layout (wide vs centered)
- Add more visualizations
- Include export functionality
- Customize styling with CSS

### Deployment
Deploy your app to share with others:
```bash
# Streamlit Cloud (free)
# Push to GitHub and connect at share.streamlit.io

# Or run on server
streamlit run ec2_concrete_streamlit_app.py --server.port 8501
```

## Next Steps

1. **Try different concrete grades**: Adjust f_cm to see behavior changes
2. **Explore fiber effects**: Vary μ from 0 (plain) to 1 (full retention)
3. **Compare with design codes**: Use factor for safety considerations
4. **Extend the app**: Add material comparison, optimization, etc.

## Troubleshooting

### Port Already in Use
```bash
streamlit run ec2_concrete_streamlit_app.py --server.port 8502
```

### Module Not Found
Make sure you're in the conda environment:
```bash
conda activate icc_env
pip install -e /home/rch/Coding/bmcs_cross_section
```

### Browser Doesn't Open
Manually navigate to the URL shown in terminal (usually http://localhost:8501)
