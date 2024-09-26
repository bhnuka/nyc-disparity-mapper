import os
import sys
import geopandas
import fiona
import pyogrio
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

def find_gdal_dlls():
    potential_paths = [
        os.path.join(sys.prefix, 'Library', 'bin'),
        os.path.join(os.path.dirname(geopandas.__file__), '..', '..', 'Library', 'bin'),
        os.path.join(os.path.dirname(geopandas.__file__), '..', '..', '..', 'Library', 'bin'),
    ]
    for path in potential_paths:
        if os.path.exists(path):
            return [(os.path.join('Library', 'bin', f), os.path.join(path, f), 'BINARY') 
                    for f in os.listdir(path) if f.lower().startswith('gdal')]
    return []

gdal_dlls = find_gdal_dlls()

a = Analysis(
    ['base.py'],
    pathex=[],
    binaries=gdal_dlls,
    datas=[
        ('Police Precincts', 'Police Precincts'),
        ('nyc-data.csv', '.'),
        ('MODZCTA', 'MODZCTA'),
    ] + collect_data_files('geopandas') + collect_data_files('fiona') + collect_data_files('pyogrio'),
    hiddenimports=['geopandas', 'fiona', 'pyogrio', 'shapely', 'pyproj'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Collect all dynamic libs for geopandas, fiona, and pyogrio
a.binaries += collect_dynamic_libs('geopandas')
a.binaries += collect_dynamic_libs('fiona')
a.binaries += collect_dynamic_libs('pyogrio')

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NYCDemographics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NYCDemographics',
)
