import os
import shutil
import zipfile
from PIL import Image, ImageFile
import logging

ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger("YomiCore")

def convert_to_pdf(source_folder: str, output_path: str):
    if not os.path.exists(source_folder): return False

    files = sorted(os.listdir(source_folder))
    image_list = []
    
    for f in files:
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            full_path = os.path.join(source_folder, f)
            # CRITICAL: Ignore ghost files
            if os.path.getsize(full_path) == 0:
                continue

            try:
                img = Image.open(full_path).convert('RGB')
                image_list.append(img)
            except:
                pass 

    if not image_list:
        logger.warning(f"PDF Failed: No valid images in {source_folder}")
        return False

    try:
        image_list[0].save(output_path, save_all=True, append_images=image_list[1:])
        return True
    except Exception as e:
        logger.error(f"PDF Write Error: {e}")
        return False

def convert_to_cbz(source_folder: str, output_path: str):
    if not os.path.exists(source_folder): return False
    
    # Check for at least one good file
    has_files = False
    for f in os.listdir(source_folder):
        if os.path.getsize(os.path.join(source_folder, f)) > 0:
            has_files = True
            break
            
    if not has_files: return False

    try:
        with zipfile.ZipFile(output_path, 'w') as cbz:
            for root, dirs, files in os.walk(source_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.getsize(file_path) > 0:
                        cbz.write(file_path, arcname=file)
        return True
    except:
        return False