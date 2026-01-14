#!/usr/bin/env python3
"""
Bundle Admin UI into ContextForge package.

This script copies the built admin UI files into the contextforge package
so they can be served as static files when the library is installed.

Usage:
    # From the faq root directory:
    
    # 1. Build the admin UI
    cd admin-ui && npm run build && cd ..
    
    # 2. Bundle into contextforge
    python contextforge/scripts/bundle_admin_ui.py
    
    # 3. Build the package
    pip install build
    python -m build contextforge/

The bundled files will be at:
    contextforge/contextforge/admin/
    
And served at /admin when admin_ui_enabled=True.
"""

import shutil
import sys
from pathlib import Path


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # faq/
    
    admin_ui_dist = project_root / "admin-ui" / "dist"
    contextforge_admin = script_dir.parent / "contextforge" / "admin"
    
    print(f"Source: {admin_ui_dist}")
    print(f"Destination: {contextforge_admin}")
    
    if not admin_ui_dist.exists():
        print("\nError: Admin UI dist not found.")
        print("Run the following commands first:")
        print("  cd admin-ui")
        print("  npm install")
        print("  npm run build")
        sys.exit(1)
    
    if contextforge_admin.exists():
        print(f"\nRemoving existing bundle: {contextforge_admin}")
        shutil.rmtree(contextforge_admin)
    
    print(f"\nCopying admin UI files...")
    shutil.copytree(admin_ui_dist, contextforge_admin)
    
    index_html = contextforge_admin / "index.html"
    if index_html.exists():
        print(f"  - index.html: OK")
    else:
        print(f"  - WARNING: index.html not found")
    
    assets_dir = contextforge_admin / "assets"
    if assets_dir.exists():
        asset_count = len(list(assets_dir.glob("*")))
        print(f"  - assets/: {asset_count} files")
    
    total_size = sum(f.stat().st_size for f in contextforge_admin.rglob("*") if f.is_file())
    print(f"\nTotal size: {total_size / 1024 / 1024:.2f} MB")
    
    print("\nAdmin UI bundled successfully!")
    print("\nNext steps:")
    print("  1. Build the package: python -m build contextforge/")
    print("  2. Install: pip install contextforge/dist/contextforge-*.whl")
    print("  3. Access Admin UI at: http://localhost:8000/admin")


if __name__ == "__main__":
    main()
