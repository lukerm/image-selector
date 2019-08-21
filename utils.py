"""
"""

## Imports ##

import os
import shutil


static_image_route = '/'



## Functions ##


# File manipulations #

def copy_image(fname, src_path, dst_path, image_types):
    """
    Perform a copy of the file if it is an image. It will be copied to dst_path.

    Args:
        fname = str, query filename (no path)
        src_path = str, directory of where to copy from (no filename)
        dst_path = str, directory of where to copy to (no filename)

    Returns: str, full filepath that the server is expecting
             or None, if not an valid image type (see IMAGE_TYPES)
    """

    # Check if it's a valid image (by extension)
    is_image = False
    for img_type in image_types:
        if img_type in fname:
            is_image = True
            break
    # Only copy images
    if not is_image:
        # Warning on non-directory filenames
        if len(fname.split('.')) > 1:
            print(f"WARNING: ignoring non-image file {fname}")
        return

    # Copy the file to the temporary location (that can be served)
    shutil.copyfile(os.path.join(src_path, fname), os.path.join(dst_path, fname))
    # Append the Img object with the static path
    static_image_path = os.path.join(static_image_route, fname)

    return static_image_path