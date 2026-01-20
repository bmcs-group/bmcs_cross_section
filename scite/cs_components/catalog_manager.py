"""
Catalog Manager - Caching System for Component Catalogs

Provides persistent storage and lazy loading of component catalogs.
Mimics object-oriented database pattern with cached instances.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


class CatalogManager:
    """
    Singleton manager for component catalog caching.
    
    Features:
    - Lazy loading: catalogs loaded only when needed
    - JSON persistence: catalogs stored in cache directory
    - Automatic refresh: detects stale catalogs
    - Memory cache: keeps loaded catalogs in memory
    
    Usage:
        >>> manager = CatalogManager.get_instance()
        >>> steel_catalog = manager.get_steel_catalog()
        >>> concrete = manager.get_concrete_by_class('C30/37')
    """
    
    _instance: Optional['CatalogManager'] = None
    _cache_dir: Path = Path(__file__).parent / '.catalog_cache'
    
    def __init__(self):
        """Initialize catalog manager (use get_instance() instead)."""
        # In-memory cache
        self._catalogs: Dict[str, pd.DataFrame] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        
        # Ensure cache directory exists
        self._cache_dir.mkdir(exist_ok=True)
        
        # Load metadata
        self._load_metadata()
    
    @classmethod
    def get_instance(cls) -> 'CatalogManager':
        """Get singleton instance of catalog manager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (useful for testing)."""
        cls._instance = None
    
    def _load_metadata(self):
        """Load catalog metadata from cache."""
        metadata_file = self._cache_dir / 'metadata.json'
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                self._metadata = json.load(f)
    
    def _save_metadata(self):
        """Save catalog metadata to cache."""
        metadata_file = self._cache_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self._metadata, f, indent=2)
    
    def _get_cache_path(self, catalog_name: str) -> Path:
        """Get cache file path for catalog."""
        return self._cache_dir / f'{catalog_name}.json'
    
    def _compute_catalog_hash(self, catalog_df: pd.DataFrame) -> str:
        """Compute hash of catalog data for change detection."""
        # Convert to JSON string and hash
        data_str = catalog_df.to_json(orient='records')
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _is_cache_valid(self, catalog_name: str) -> bool:
        """Check if cached catalog exists and is valid."""
        cache_path = self._get_cache_path(catalog_name)
        if not cache_path.exists():
            return False
        
        # Check metadata
        if catalog_name not in self._metadata:
            return False
        
        # Cache is valid if file exists
        return True
    
    def _load_from_cache(self, catalog_name: str) -> Optional[pd.DataFrame]:
        """Load catalog from JSON cache."""
        cache_path = self._get_cache_path(catalog_name)
        
        if not cache_path.exists():
            return None
        
        try:
            # Read JSON and convert to DataFrame
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            df = pd.DataFrame(data['records'])
            
            # Update metadata with access time
            if catalog_name in self._metadata:
                self._metadata[catalog_name]['last_accessed'] = datetime.now().isoformat()
                self._save_metadata()
            
            return df
        
        except Exception as e:
            print(f"Warning: Failed to load catalog {catalog_name} from cache: {e}")
            return None
    
    def _save_to_cache(self, catalog_name: str, catalog_df: pd.DataFrame):
        """Save catalog to JSON cache."""
        cache_path = self._get_cache_path(catalog_name)
        
        try:
            # Convert DataFrame to JSON-serializable format
            data = {
                'catalog_name': catalog_name,
                'created': datetime.now().isoformat(),
                'records': catalog_df.to_dict(orient='records'),
                'columns': list(catalog_df.columns),
                'count': len(catalog_df)
            }
            
            # Write to file
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Update metadata
            catalog_hash = self._compute_catalog_hash(catalog_df)
            self._metadata[catalog_name] = {
                'created': data['created'],
                'last_accessed': data['created'],
                'count': data['count'],
                'hash': catalog_hash,
                'cache_file': str(cache_path)
            }
            self._save_metadata()
            
        except Exception as e:
            print(f"Warning: Failed to save catalog {catalog_name} to cache: {e}")
    
    def _get_or_create_catalog(
        self, 
        catalog_name: str, 
        creator_func: callable
    ) -> pd.DataFrame:
        """
        Get catalog from memory cache, disk cache, or create new.
        
        Args:
            catalog_name: Name of catalog
            creator_func: Function to create catalog if not cached
            
        Returns:
            DataFrame with catalog data
        """
        # Check memory cache first
        if catalog_name in self._catalogs:
            return self._catalogs[catalog_name]
        
        # Try loading from disk cache
        if self._is_cache_valid(catalog_name):
            catalog_df = self._load_from_cache(catalog_name)
            if catalog_df is not None:
                # Store in memory cache
                self._catalogs[catalog_name] = catalog_df
                return catalog_df
        
        # Create new catalog
        print(f"Creating catalog: {catalog_name}")
        catalog_df = creator_func()
        
        # Save to disk cache
        self._save_to_cache(catalog_name, catalog_df)
        
        # Store in memory cache
        self._catalogs[catalog_name] = catalog_df
        
        return catalog_df
    
    def invalidate_catalog(self, catalog_name: str):
        """
        Invalidate cached catalog (will be recreated on next access).
        
        Args:
            catalog_name: Name of catalog to invalidate
        """
        # Remove from memory cache
        if catalog_name in self._catalogs:
            del self._catalogs[catalog_name]
        
        # Remove from disk cache
        cache_path = self._get_cache_path(catalog_name)
        if cache_path.exists():
            cache_path.unlink()
        
        # Remove from metadata
        if catalog_name in self._metadata:
            del self._metadata[catalog_name]
            self._save_metadata()
    
    def clear_all_caches(self):
        """Clear all cached catalogs."""
        # Clear memory cache
        self._catalogs.clear()
        
        # Clear disk cache
        for cache_file in self._cache_dir.glob('*.json'):
            if cache_file.name != 'metadata.json':
                cache_file.unlink()
        
        # Clear metadata
        self._metadata.clear()
        self._save_metadata()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached catalogs."""
        return {
            'cache_dir': str(self._cache_dir),
            'memory_cached': list(self._catalogs.keys()),
            'disk_cached': list(self._metadata.keys()),
            'metadata': self._metadata.copy()
        }
    
    # ===================================================================
    # Catalog-specific methods
    # ===================================================================
    
    def get_steel_catalog(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Get steel rebar catalog.
        
        Args:
            force_refresh: Force recreation of catalog
            
        Returns:
            DataFrame with steel rebar components
        """
        if force_refresh:
            self.invalidate_catalog('steel_rebars')
        
        from scite.cs_components.steel_rebars import create_steel_rebar_catalog

        # Pass use_cache=False to avoid infinite recursion
        return self._get_or_create_catalog(
            'steel_rebars', 
            lambda: create_steel_rebar_catalog(use_cache=False)
        )
    
    def get_carbon_catalog(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Get carbon bar catalog.
        
        Args:
            force_refresh: Force recreation of catalog
            
        Returns:
            DataFrame with carbon bar components
        """
        if force_refresh:
            self.invalidate_catalog('carbon_bars')
        
        from scite.cs_components.carbon_bars import create_carbon_bar_catalog
        return self._get_or_create_catalog(
            'carbon_bars', 
            lambda: create_carbon_bar_catalog(use_cache=False)
        )
    
    def get_textile_catalog(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Get textile reinforcement catalog.
        
        Args:
            force_refresh: Force recreation of catalog
            
        Returns:
            DataFrame with textile components
        """
        if force_refresh:
            self.invalidate_catalog('textile_products')
        
        from scite.cs_components.textile_products import create_textile_catalog
        return self._get_or_create_catalog(
            'textile_products', 
            lambda: create_textile_catalog(use_cache=False)
        )
    
    def get_concrete_catalog(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Get concrete catalog.
        
        Args:
            force_refresh: Force recreation of catalog
            
        Returns:
            DataFrame with concrete components
        """
        if force_refresh:
            self.invalidate_catalog('concrete')
        
        from scite.cs_components.concrete_catalog import \
            create_concrete_catalog
        return self._get_or_create_catalog(
            'concrete', 
            lambda: create_concrete_catalog(use_cache=False)
        )
    
    def get_concrete_by_class(self, strength_class: str) -> Optional[Any]:
        """
        Get concrete component by strength class.
        
        Args:
            strength_class: EC2 strength class (e.g., "C30/37")
            
        Returns:
            ConcreteComponent or None if not found
        """
        catalog = self.get_concrete_catalog()
        result = catalog[catalog['strength_class'] == strength_class]
        
        if result.empty:
            return None
        
        row = result.iloc[0]
        
        # Recreate component from cached data
        from scite.cs_components.concrete_catalog import ConcreteComponent
        from scite.matmod.ec2_parabola_rectangle import EC2ParabolaRectangle
        
        matmod = EC2ParabolaRectangle(f_ck=row['f_ck'], alpha_cc=0.85, gamma_c=1.5)
        
        return ConcreteComponent(
            product_id=row['product_id'],
            name=row['name'],
            strength_class=row['strength_class'],
            f_ck=row['f_ck'],
            f_cm=row['f_cm'],
            E_cm=row['E_cm'],
            gamma_c=row.get('gamma_c', 1.5),
            alpha_cc=row.get('alpha_cc', 1.0),
            matmod=matmod,
        )
    
    def get_steel_by_id(self, product_id: str) -> Optional[Any]:
        """
        Get steel rebar component by product ID.
        
        Args:
            product_id: Product ID (e.g., "REBAR-B500B-D20")
            
        Returns:
            SteelRebarComponent or None if not found
        """
        catalog = self.get_steel_catalog()
        result = catalog[catalog['product_id'] == product_id]
        
        if result.empty:
            return None
        
        row = result.iloc[0]
        
        # Recreate component from cached data
        from scite.cs_components.steel_rebars import SteelRebarComponent
        
        return SteelRebarComponent(
            product_id=row['product_id'],
            name=row['name'],
            nominal_diameter=row['nominal_diameter'],
            grade=row['grade'],
        )


# Module-level convenience functions
def get_catalog_manager() -> CatalogManager:
    """Get the catalog manager instance."""
    return CatalogManager.get_instance()
