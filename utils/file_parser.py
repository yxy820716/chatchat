import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Union
import re
from typing import List, Dict, Any, Iterable, Set, Optional
import numpy as np
from pdf2image import convert_from_path
from paddleocr import PPStructureV3
# https://www.paddlepaddle.org.cn/documentation/docs/zh/install/index_cn.html
# GPUpaddle安装
try:
    from docx2pdf import convert as docx2pdf_convert
    HAS_DOCX2PDF = True
except Exception:
    HAS_DOCX2PDF = False
import os

BASE = "./configs/official_models"

pipeline = PPStructureV3(
    device="gpu:0",

    # 开关保持你给的
    use_region_detection=True,
    use_table_recognition=True,
    use_formula_recognition=True,
    use_chart_recognition=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    use_seal_recognition=False,

    # 版面 & 区域（layout 用 DocLayout_plus-L，region 用 DocBlockLayout）
    layout_detection_model_name="PP-DocLayout_plus-L",
    layout_detection_model_dir=f"{BASE}/PP-DocLayout_plus-L",
    region_detection_model_name="PP-DocBlockLayout",
    region_detection_model_dir=f"{BASE}/PP-DocBlockLayout",

    # OCR（检测 + 识别）
    text_detection_model_name="PP-OCRv5_server_det",
    text_detection_model_dir=f"{BASE}/PP-OCRv5_server_det",
    text_recognition_model_name="PP-OCRv5_server_rec",
    text_recognition_model_dir=f"{BASE}/PP-OCRv5_server_rec",

    # 可选分类器（先关着用也没事，路径先配好）
    doc_orientation_classify_model_name="PP-LCNet_x1_0_doc_ori",
    doc_orientation_classify_model_dir=f"{BASE}/PP-LCNet_x1_0_doc_ori",
    textline_orientation_model_name="PP-LCNet_x1_0_textline_ori",
    textline_orientation_model_dir=f"{BASE}/PP-LCNet_x1_0_textline_ori",

    # 表格识别（分类 + 结构识别 + 单元格检测）
    table_classification_model_name="PP-LCNet_x1_0_table_cls",
    table_classification_model_dir=f"{BASE}/PP-LCNet_x1_0_table_cls",

    wired_table_structure_recognition_model_name="SLANeXt_wired",
    wired_table_structure_recognition_model_dir=f"{BASE}/SLANeXt_wired",
    wireless_table_structure_recognition_model_name="SLANet_plus",
    wireless_table_structure_recognition_model_dir=f"{BASE}/SLANet_plus",

    wired_table_cells_detection_model_name="RT-DETR-L_wired_table_cell_det",
    wired_table_cells_detection_model_dir=f"{BASE}/RT-DETR-L_wired_table_cell_det",
    wireless_table_cells_detection_model_name="RT-DETR-L_wireless_table_cell_det",
    wireless_table_cells_detection_model_dir=f"{BASE}/RT-DETR-L_wireless_table_cell_det",

    # 公式 & 图表（你关了图表，但先把路径也配好）
    formula_recognition_model_name="PP-FormulaNet_plus-L",
    formula_recognition_model_dir=f"{BASE}/PP-FormulaNet_plus-L",
    chart_recognition_model_name="PP-Chart2Table",
    chart_recognition_model_dir=f"{BASE}/PP-Chart2Table",
)

class PPOCRMarkdownParser:
    def __init__(
        self,
        pdf_dpi: int = 300,
        # poppler_path: Union[str, None] = None,
        # poppler_path="./poppler-25.07.0/Library/bin"
        poppler_path= None


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

        # 1) 纯 markdown 直读
        if ext == ".md":
            text = p.read_text(encoding="utf-8", errors="ignore")
            return {"markdown": text, "pages": [text], "images": []}

        # 2) 直接 PDF：用 PPStructureV3 解析
        if ext == ".pdf":
            return self._parse_pdf(p)

        # 3) 常见图片：用 PPStructureV3 解析
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"):
            return self._parse_image(p)

        # 4) DOCX：先转成 PDF，再用 PPStructureV3 解析 PDF
        if ext == ".docx":
            pdf_path = self._docx_to_pdf(p)  # 生成临时/目标 PDF
            try:
                result = self._parse_pdf(pdf_path)
            finally:
                # 如果是我们创建的临时 PDF，则解析后删除，避免脏文件
                if pdf_path.suffix == ".pdf" and pdf_path.name.endswith(".__tmp_ppocr__.pdf") and pdf_path.exists():
                    try:
                        pdf_path.unlink()
                    except Exception:
                        pass
            return result

        raise ValueError(f"不支持的文件类型：{ext}（支持 docx / pdf / 常见图片 / md）")

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

    # =============== PDF 解析（核心） ===============
    def _parse_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        outputs = self.pipeline.predict(str(pdf_path))
        markdown_list = []
        markdown_images = []

        for res in outputs:
            md_info = res.markdown
            markdown_list.append(md_info)
            markdown_images.append(md_info.get("markdown_images", {}))

        markdown_texts = pipeline.concatenate_markdown_pages(markdown_list)

        return {"markdown": markdown_texts}

    # =============== 图片 解析 ===============
    def _parse_image(self, image_path: Path) -> Dict[str, Any]:
        outputs = self.pipeline.predict(str(image_path))
        markdown_list = []
        for i in outputs:
            markdown_list.append(i.markdown)
        markdown_texts = pipeline.concatenate_markdown_pages(markdown_list)
        # 图片大概率只有一个“页”结果，但为了稳妥按列表处理
        return {"markdown": markdown_texts}

    # =============== 兼容旧接口：PDF -> 纯文本 ===============
    def pdf_to_texts(self, pdf_path: Union[str, Path]) -> str:
        """保留旧函数名，返回拼接后的 markdown 文本字符串。"""
        result = self._parse_pdf(Path(pdf_path))
        return result["markdown"]


# # # 用法示例：
# if __name__ == "__main__":
#     parser = PPOCRMarkdownParser(
#         pdf_dpi=300,
#         # poppler_path="./poppler-25.07.0/Library/bin"
#     )
#     r1 = parser.to_markdown(r"C:\Users\hello\Desktop\AI_Moku\chatchat\dataset\knowbase\files\0f8284c3-ddd8-4696-a673-4c267554ac54_1b6fd4c6f1d14e5fbdc5d7c26aaae57c_ff730f50ebd9414a9acb366e000c4a9a.png")
#     print(r1["markdown"])
