import os
import uuid
from PIL import Image
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if file has a valid extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_and_save_image(file_storage, target_folder, max_width=1200, quality=80):
    """
    Compresses, Resizes, and Saves an image file.
    
    :param file_storage: The FileStorage object from Flask request.files
    :param target_folder: Absolute path to the save directory.
    :param max_width: Maximum width in pixels (aspect ratio preserved).
    :param quality: JPG compression quality (1-100).
    :return: The new unique filename.
    """
    if not file_storage or not allowed_file(file_storage.filename):
        raise ValueError("Invalid file type.")

    # 1. Generate Unique Filename
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(target_folder, unique_filename)

    # 2. Open Image using Pillow
    try:
        img = Image.open(file_storage)

        # 3. Resize if the image is wider than max_width
        if img.width > max_width:
            w_percent = (max_width / float(img.width))
            h_size = int((float(img.height) * float(w_percent)))
            # LANCZOS is the high-quality downsampling filter
            img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)

        # 4. Save & Compress
        os.makedirs(target_folder, exist_ok=True)

        if ext in ['jpg', 'jpeg']:
            # Convert mode to RGB (handles RGBA pngs converted to jpg)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(save_path, 'JPEG', quality=quality, optimize=True)
            
        elif ext == 'png':
            # PNG compression is handled via optimize=True (lossless) 
            # or reducing colors (quantize), here we stick to optimize
            img.save(save_path, 'PNG', optimize=True)
            
        elif ext == 'gif':
            img.save(save_path, save_all=True, optimize=True)

        return unique_filename

    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")