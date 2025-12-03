from pathlib import Path
import shutil
import fitz
import json
import pdfplumber
from ...log.logger import logger



def extract_image(pdf_path=None, out_dir="./pdf_pro/images"):
    pdf_dir = Path(pdf_path) if pdf_path else Path(__file__).resolve().parent / "out_shards"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_images = []
    for pdf_file in pdf_dir.glob("*.pdf"):
        with fitz.open(pdf_file) as doc:
            for page_index in range(len(doc)):
                page = doc[page_index]
                image_list = page.get_images(full=True)

                for image_index, imag in enumerate(image_list, start=1):
                    xref = imag[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    filename = f"{pdf_file.stem}-page-{page_index + 1}-image-{image_index}.{image_ext}"
                    out_path = out_dir / filename
                    out_path.write_bytes(image_bytes)

                    all_images.append({
                        "pdf": pdf_file.name,
                        "page": page_index + 1,
                        "image_id": f"{page_index + 1}-{image_index}",
                        "filename": str(out_path),
                    })

    return all_images


def extract_text_and_images(pdf_path=None, work_dir = "./pdf_pro"):
    pdf_dir = pdf_path if pdf_path else Path(__file__).resolve().parent / "out_shards"
    image_out_dir = Path(work_dir) / "images"
    text_out_dir = Path(work_dir) / "texts"
    text_out_dir.mkdir(parents=True, exist_ok=True)
    image_out_dir.mkdir(parents=True, exist_ok=True)

    image_metadata = extract_image(pdf_path=pdf_dir, out_dir=image_out_dir)

    text_metadata = []
    for pdf_file in pdf_dir.glob("*.pdf"):
        with pdfplumber.open(pdf_file) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                sheet = page.extract_tables()
                text_file = text_out_dir / f"{pdf_file.stem}-page-{page_index}.txt"
                content = text
                if sheet:
                    content = f"{text}\n\nTables:\n{json.dumps(sheet, ensure_ascii=False, indent=2)}"
                text_file.write_text(content, encoding="utf-8")

                text_metadata.append({
                    "pdf": pdf_file.name,
                    "page": page_index,
                    "filename": str(text_file),
                })

    (text_out_dir / "PDF.json").write_text(json.dumps({"image": image_metadata, "text": text_metadata}, ensure_ascii=False, indent=2), encoding="utf-8")


def _move_to_save(update_dir: Path, save_path: Path) -> None:
    """Move processed files from the update box into the main shard directory."""
    save_path.mkdir(parents=True, exist_ok=True)
    for src in update_dir.glob("*"):
        if not src.is_file():
            continue
        dest = save_path / src.name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dest)  # overwrite existing
        except Exception:
            # fall back to shutil in case replace fails across filesystems
            shutil.move(str(src), str(dest))


def local_doc_process(update_dir: Path | None = None):
    if not update_dir.glob("*"):
        logger.warning("no file need update")
        return [], []
    pdf_woark_dir = Path(__file__).resolve().parent / "pdf_pro"

    def _collect(shard_dir: Path):
        files = sorted(shard_dir.glob("*.txt"))
        extract_text_and_images(pdf_path=shard_dir, work_dir=pdf_woark_dir)
        pdf_text = pdf_woark_dir / "texts"
        content = files + sorted(pdf_text.glob("*.txt"))
        image_path = pdf_woark_dir / "images"
        images = sorted(image_path.glob("*.*"))
        return content, images

    # Prefer processing the update box, then move its files into save_path
    if update_dir and Path(update_dir).exists():
        update_path = Path(update_dir)
        content, images = _collect(update_path)
        return content, images

    print("no file need update or update path error")
    return [], []
