import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Union
import re
from typing import List, Dict, Any, Iterable, Set, Optional
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from paddleocr import PPStructureV3
from sklearn.linear_model import PassiveAggressiveRegressor
# https://www.paddlepaddle.org.cn/documentation/docs/zh/install/index_cn.html
# GPUpaddle安装
try:
    from docx2pdf import convert as docx2pdf_convert
    HAS_DOCX2PDF = True
except Exception:
    HAS_DOCX2PDF = False
import os


pipeline = PPStructureV3(
    device="gpu:2,3",
    use_region_detection=True,
    use_table_recognition=True,
    use_formula_recognition=True,
    use_chart_recognition= False,
    use_doc_orientation_classify= False,
    use_doc_unwarping = False,
    use_textline_orientation = False,
    use_seal_recognition = False,
    # pdf_dpi = 300,
    # linux
    # poppler_path=None,
    
)

class PPOCRMarkdownParser:
    def __init__(
        self,
        paddlex_config: Union[str, None] = None,
        device: str = "cpu",
        use_region_detection: bool = True,
        use_table_recognition: bool = True,
        use_formula_recognition: bool = True,
        use_chart_recognition: bool = False,
        use_doc_orientation_classify: bool = False,
        use_doc_unwarping: bool = False,
        use_textline_orientation: bool = False,
        use_seal_recognition: bool = False,
        pdf_dpi: int = 300,
        poppler_path: Union[str, None] = None,   # ✅ 新增：指定 poppler 的 bin 路径（Windows）
    ):
        self.pipeline = pipeline
        self.poppler_path = poppler_path
        self.pdf_dpi = pdf_dpi
        

    # =============== 公共入口 ===============
    def to_markdown(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(p)
        ext = p.suffix.lower()

        if ext == ".md":
            text = p.read_text(encoding="utf-8", errors="ignore")
            return {"markdown": text, "pages": [text], "images": []}

        if ext == ".pdf":
            # ✅ PDF：渲染全部页为图片 → 统一走图片预测函数
            pages = convert_from_path(str(p), dpi=self.pdf_dpi, poppler_path=self.poppler_path)
            np_pages = [np.array(im) for im in pages]  # PIL -> ndarray
            return self._images_to_markdown(np_pages)

        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"):
            # ✅ 单图：也走统一预测函数（传入 list，保持接口一致）
            img = self._imread_unicode(p)  # ndarray (BGR)
            img = img[:, :, ::-1]          # 转 RGB，和 PIL/np 一致（可选，按你的 pipeline 实测而定）
            return self._images_to_markdown([img])

        if ext == ".docx":
            # ✅ DOCX：先转 PDF，再同上
            pdf_path = self._docx_to_pdf(p)
            pages = convert_from_path(str(pdf_path), dpi=self.pdf_dpi, poppler_path=self.poppler_path)
            np_pages = [np.array(im) for im in pages]
            # 若是我们创建的临时 pdf，解析后清理
            if pdf_path.name.endswith(".__tmp_ppocr__.pdf"):
                try: pdf_path.unlink()
                except Exception: pass
            return self._images_to_markdown(np_pages)

        raise ValueError(f"不支持的文件类型：{ext}（支持 docx / pdf / 常见图片 / md）")

    # =============== 核心统一通路：多张图片 -> Markdown ===============
    def _images_to_markdown(self, images_rgb: List[np.ndarray]) -> Dict[str, Any]:
        """
        接收一组 RGB ndarray（统一入口：图片、PDF页、DOCX转PDF页），
        逐页送入 pipeline.predict，最终：
        - pages: 每页 markdown 文本（markdown_text）
        - markdown: pipeline.concatenate_markdown_pages 汇总文本
        - images: 从每页结果的 markdown_images 聚合（如有）
        """
        md_objs: List[Dict[str, Any]] = []
        page_texts: List[str] = []

        for arr in images_rgb:
            # PaddleOCR 大多对 RGB/ndarray 友好；若你的版本期望 BGR，可切换 arr[:, :, ::-1]
            outs = self.pipeline.predict(arr)
            for res in outs:
                md = res.markdown  # dict: {"markdown_text": "...", "markdown_images": [...], ...}
                md_objs.append(md)
                page_texts.append(md.get("markdown_text", "") or "")

        md_text = self.pipeline.concatenate_markdown_pages(md_objs)
        return {
            "markdown": md_text,
            "pages": page_texts,
            "images": self._collect_md_images(md_objs),
        }

    # =============== 工具：DOCX -> PDF ===============
    def _docx_to_pdf(self, docx_path: Path) -> Path:
        """优先 docx2pdf（Win/Mac + Word），否则用 LibreOffice；返回生成的 PDF 路径。"""
        if HAS_DOCX2PDF:
            tmp_pdf = docx_path.with_suffix(".__tmp_ppocr__.pdf")
            docx2pdf_convert(str(docx_path), str(tmp_pdf))
            return tmp_pdf
        # 使用 soffice（需要安装 LibreOffice，并在 PATH 可用）
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", str(docx_path), "--outdir", str(docx_path.parent)],
            check=True
        )
        return docx_path.with_suffix(".pdf")

    # =============== 工具：中文路径读图（BGR） ===============
    @staticmethod
    def _imread_unicode(path: Path) -> np.ndarray:
        import cv2
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)  # BGR
        if img is None:
            raise ValueError(f"无法读取图片：{path}")
        return img

    # =============== 工具：聚合 markdown_images ===============
    @staticmethod
    def _collect_md_images(md_objs: List[Dict[str, Any]]) -> List[str]:
        links: List[str] = []
        for md in md_objs:
            imgs = md.get("markdown_images") or []
            if isinstance(imgs, dict):
                links.extend([str(v) for v in imgs.values()])
            elif isinstance(imgs, (list, tuple)):
                links.extend([str(x) for x in imgs])
        # 去重保持顺序
        seen, uniq = set(), []
        for x in links:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq
    
    def md_split():
        HEADING_RE = re.compile(r'^(#{1,4})\s+(.+?)\s*#*\s*$')  # 只匹配 #..####（最多4个#）
        FENCE_OPEN_RE = re.compile(r'^([`~]{3,})(.*)$')         # ``` 或 ~~~ 开头的围栏代码块






# if __name__ == "__main__":
    # parser = PPOCRMarkdownParser(
    # # 你也可以用 paddlex_config="PP-StructureV3.yaml" 全量控制加载地址
    # device="cpu",
    # # gpu:0,1,2,3）可实现多卡并行推理
    # use_region_detection=True,
    # use_table_recognition=True,
    # use_formula_recognition=True,
    # poppler_path="./poppler-25.07.0/Library/bin"
    # )
    # r3 = parser.to_markdown(r"C:\Users\Yy\Desktop\agent\chatchat\utils\你好.png")
    # print(r3["markdown"])