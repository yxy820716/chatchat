import os
import sys
from pathlib import Path

import PyInstaller.__main__

# 项目入口文件
ENTRY_FILE = 'main.py'
APP_NAME = 'chatchat'

# 不需要打包的用户目录（运行时将在同级目录下生成/使用）
EXCLUDE_DIRS = [
    os.path.join('dataset', 'history'),
    os.path.join('dataset', 'knowbase')
]

# 静态资源目录，需要随 exe 一起打包
STATIC_DIR = Path('dist')

# OCR 官方模型目录，需要打包以便离线运行
OCR_MODEL_DIR = Path('configs') / 'official_models'


def build():
    opts = [
        ENTRY_FILE,
        '--name', APP_NAME,
        '--noconfirm',
        '--clean',
        '--collect-all', 'paddleocr',
        '--hidden-import', 'paddleocr',
        '--hidden-import', 'pdf2image',
        '--add-data', f'{STATIC_DIR}{os.pathsep}dist',
        '--add-data', f'{OCR_MODEL_DIR}{os.pathsep}configs/official_models',
        '--onefile',
    ]

    for d in EXCLUDE_DIRS:
        # 排除用户目录
        opts.append(f'--exclude-module={d.replace(os.sep, ".")}')

    PyInstaller.__main__.run(opts)


if __name__ == '__main__':
    """使用 PyInstaller 将项目打包为单个 exe.

    在运行此脚本前，请确保安装 GPU 版本的 PaddleOCR：

        pip install --upgrade pip
        pip install paddlepaddle-gpu paddleocr

    然后执行:

        python build_exe.py

    OCR 模型应放在 ``configs/official_models`` 目录下，脚本会将该目录一起打包。
    """
    build()
