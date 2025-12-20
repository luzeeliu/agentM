from pathlib import Path
import shutil
import fitz
import json
import pdfplumber
from ...log.logger import logger



def extract_image(pdf_path=None, out_dir="./pdf_pro/images"):
    # the pdf_path is absolute path of a PDF
    if pdf_path:
        pdf_file = Path(pdf_path)
    else:
        logger.warning("pdf_path is None")
        raise KeyError("pdf_path is None")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_images = []

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

                # Store relative path for portability
                try:
                    # Calculate path relative to the work_dir (parent of out_dir)
                    # out_dir is work_dir/images, so out_dir.parent is work_dir
                    rel_path = out_path.relative_to(Path(out_dir).parent)
                except ValueError:
                    rel_path = out_path.name

                all_images.append({
                    "pdf": pdf_file.name,
                    "page": page_index + 1,
                    "image_id": f"{page_index + 1}-{image_index}",
                    "filename": str(rel_path).replace("\\", "/"),
                })

    return all_images


def extract_text_and_images(pdf_path=None, work_dir = "./pdf_pro"):
    # pdf_path is absolute path of a PDF
    if not pdf_path:
        logger.error("don't find pdf document")
        raise KeyError("pdf_path is None")
    pdf_file = Path(pdf_path)
    work_dir_path = Path(work_dir)
    image_out_dir = work_dir_path / "images"
    text_out_dir = work_dir_path / "texts"
    text_out_dir.mkdir(parents=True, exist_ok=True)
    image_out_dir.mkdir(parents=True, exist_ok=True)

    image_metadata = extract_image(pdf_path=pdf_file, out_dir=image_out_dir)

    text_metadata = []
    text_paths: list[Path] = []
    image_paths = [Path(img["filename"]) for img in image_metadata]
    with pdfplumber.open(pdf_file) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            # Normalize layout to avoid pdfminer/pdfplumber tuple_iterator errors
            if getattr(page, "layout", None) and hasattr(page.layout, "_objs"):
                try:
                    page.layout._objs = list(page.layout._objs)
                except TypeError:
                    page.layout._objs = list(page.layout)

            try:
                text = page.extract_text() or ""
            except TypeError:
                logger.warning("pdfplumber extract_text failed; falling back to fitz on page %s", page_index)
                with fitz.open(pdf_file) as f:
                    text = f.load_page(page_index - 1).get_text()

            sheet = page.extract_tables()
            text_file = text_out_dir / f"{pdf_file.stem}-page-{page_index}.txt"
            content = text
            if sheet:
                content = f"{text}\n\nTables:\n{json.dumps(sheet, ensure_ascii=False, indent=2)}"
            text_file.write_text(content, encoding="utf-8")
            text_paths.append(text_file)

            text_metadata.append({
                "pdf": pdf_file.name,
                "page": page_index,
                "filename": str(text_file.relative_to(work_dir_path)).replace("\\", "/"),
            })

    (work_dir_path / "PDF.json").write_text(json.dumps({"image": image_metadata, "text": text_metadata}, ensure_ascii=False, indent=2), encoding="utf-8")
    return text_paths, image_paths

# care if move path it will not work
# current deprecated
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
    # loop one time for file proprecess
    
    if not update_dir:
        logger.warning("no file need update")
        return [], []
    update_path = Path(update_dir)
    if not update_path.exists():
        logger.warning("update path error")
        return [], []

    pdf_work_dir = Path(__file__).resolve().parent / "pdf_pro"
    pdf_work_dir.mkdir(parents=True, exist_ok=True)

    def _collect(shard_dir: Path):
        content: list[Path] = []
        images: list[Path] = []
        for file in shard_dir.iterdir():
            if not file.is_file():
                continue
            suffix = file.suffix.lower()
            if suffix == ".pdf":
                text_paths, image_paths = extract_text_and_images(pdf_path=file, work_dir=pdf_work_dir)
                content.extend(text_paths)
                images.extend(image_paths)
            elif suffix == ".txt":
                content.append(file)
            elif suffix == ".csv":
                content.append(file)
            elif suffix == ".json":
                content.append(file)
        return content, images

    content, images = _collect(update_path)
    if not content:
        logger.warning("no file need update")
    if not images:
        logger.warning("no image need update")
    return content, images
