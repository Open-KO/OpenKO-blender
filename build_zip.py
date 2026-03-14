"""Build a clean extension zip for Blender."""
import zipfile
import os

with zipfile.ZipFile('openko_blender.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('openko_blender'):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.pyc'):
                continue
            filepath = os.path.join(root, f)
            arcname = filepath.replace(os.sep, '/')
            zf.write(filepath, arcname)

with zipfile.ZipFile('openko_blender.zip', 'r') as zf:
    for name in zf.namelist():
        print(name)