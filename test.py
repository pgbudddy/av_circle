from PIL import Image
import os


for i in range(100, 102):
    source_dir = 'static/images/product_images/'+str(i)+'/'
    for filename in os.listdir(source_dir):
        if filename.endswith(".jpeg"):
            img = Image.open(os.path.join(source_dir, filename))
            webp_name = filename.replace('.jpeg', '.webp')
            img.save(os.path.join(source_dir, webp_name), 'webp', quality=10)


# import os

# base_dir = 'static/images/product_images/'

# for i in range(1, 101):
#     folder_path = os.path.join(base_dir, str(i))
#     if os.path.isdir(folder_path):
#         image_files = [
#             f for f in os.listdir(folder_path)
#             if f.lower().endswith(('.webp'))
#         ]
#         image_files.sort(key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else x)

#         if image_files:
#             print(f"foldername: {i}")
#             print(f"file name: {', '.join(image_files)}\n")

