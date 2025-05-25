from PIL import Image
import os


for i in range(79, 150):
    source_dir = 'static/images/product_images/'+str(i)+'/'
    for filename in os.listdir(source_dir):
        if filename.endswith(".jpeg"):
            img = Image.open(os.path.join(source_dir, filename))
            webp_name = filename.replace('.jpeg', '.webp')
            img.save(os.path.join(source_dir, webp_name), 'webp', quality=10)