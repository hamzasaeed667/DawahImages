import os
import fitz

PDF_PATH = "Purification of the mind by Qadir al-Jilani.pdf"
OUTPUT_DIR = "PurificationOfMind_Images"
START_PAGE = 11
END_PAGE = 179
DPI = 150

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)
total_pages = len(doc)
print(f"Opened PDF '{PDF_PATH}' with {total_pages} total pages.")
print(f"Extracting pages {START_PAGE} to {END_PAGE} into '{OUTPUT_DIR}'...")

count = 0
for page_num in range(START_PAGE, END_PAGE + 1):
    # PyMuPDF uses 0-indexed page numbers (page 11 is index 10)
    page_idx = page_num - 1
    if page_idx >= total_pages:
        print(f"Warning: Page {page_num} exceeds total pages ({total_pages}).")
        break

    page = doc[page_idx]
    pix = page.get_pixmap(dpi=DPI)
    
    # Save image with padded page number filename
    filename = f"page_{page_num:03d}.jpg"
    filepath = os.path.join(OUTPUT_DIR, filename)
    pix.save(filepath)
    count += 1

print(f"\nSuccessfully generated {count} images in '{OUTPUT_DIR}'.")
