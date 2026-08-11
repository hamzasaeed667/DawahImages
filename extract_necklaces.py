import os
import fitz

pdf_path = "/Users/mac/Downloads/Necklaces of Gems Shaikh Muhammad ibn Yahya at-Tafidi.pdf"
output_dir = "images"
start_page = 30
end_page = 586
dpi = 150
start_img_num = 748

os.makedirs(output_dir, exist_ok=True)

doc = fitz.open(pdf_path)
total_pages = len(doc)
print(f"Opened PDF: '{pdf_path}' ({total_pages} total pages)")
print(f"Extracting PDF pages {start_page} to {end_page} into '{output_dir}' starting at image {start_img_num:03d}.jpg...")

count = 0
for page_num in range(start_page, end_page + 1):
    page_idx = page_num - 1 # PyMuPDF 0-indexed
    if page_idx >= total_pages:
        print(f"Page {page_num} out of bounds.")
        break

    page = doc[page_idx]
    pix = page.get_pixmap(dpi=dpi)

    img_num = start_img_num + count
    filename = f"{img_num:03d}.jpg"
    filepath = os.path.join(output_dir, filename)
    pix.save(filepath)
    count += 1

    if count % 50 == 0 or page_num == end_page:
        print(f"  Progress: {count}/{end_page - start_page + 1} images generated (latest: {filename})", flush=True)

print(f"\nSuccessfully rendered and saved {count} images to '{output_dir}'!")
print(f"Image range: {start_img_num:03d}.jpg to {start_img_num + count - 1:03d}.jpg")
