FROM python:3.12-slim-bookworm

# Install Noto fonts for CJK and Vietnamese/Latin PDF text insertion (Phase 3+)
# Install now so Phase 3 doesn't need a Dockerfile change (per CLAUDE.md)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      fonts-noto-cjk fonts-noto fontconfig \
      libgl1 libglib2.0-0 libgomp1 \
      libsm6 libxext6 libxrender1 && \
    fc-cache -f && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast Python dependency management
RUN pip install uv --no-cache-dir

WORKDIR /backend

# Copy dependency manifest first (layer cache: only reinstalls when pyproject.toml changes)
COPY pyproject.toml .

# Install all dependencies (including test extras) into the system Python
RUN uv pip install --system -e ".[test]"

# Phase 4: PaddleOCR CPU + fpdf2 install (D-04-16)
# paddlepaddle MUST be installed from Alibaba index (standard PyPI version is a stub)
# Threat model T-04-02: explicit -i flag prevents wrong-index install
RUN python -m pip install paddlepaddle==3.0.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# paddleocr base + paddlex[ocr] extras (PP-StructureV3 pipeline dependencies)
# paddlex[ocr] pulls in lanms, opencv, layout/table/orientation models, etc.
RUN python -m pip install "paddleocr>=3.5,<4" "fpdf2>=2.7,<3" && \
    PADDLEX_VERSION=$(python -c "import paddlex; print(paddlex.__version__)") && \
    python -m pip install "paddlex[ocr]==${PADDLEX_VERSION}"

# Phase 4: Bundle Noto fonts for fpdf2 explicit-path registration (D-04-27)
# System apt Noto fonts remain for PyMuPDF; this bundle ensures fpdf2 path works
COPY fonts/ /backend/fonts/

# Phase 4: Bake PP-StructureV3 models at build time (D-04-15)
# Models download to /paddle_models (~700MB-1GB). Prevents demo-day cold-start.
# Threat model T-04-03: pinned paddlepaddle==3.0.0; no runtime model downloads.
ENV PADDLEOCR_HOME=/paddle_models
RUN python -c "from paddleocr import PPStructureV3; PPStructureV3(device='cpu', text_detection_model_name='PP-OCRv5_mobile_det', text_recognition_model_name='PP-OCRv5_mobile_rec', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, use_seal_recognition=False, use_chart_recognition=False, use_table_recognition=False, use_formula_recognition=False)"

# Copy alembic config — needed by `alembic current/upgrade` invoked via docker exec
COPY alembic.ini .

# Copy source code (bind-mounted in development; baked in production builds)
COPY src/ src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/backend/src

EXPOSE 8000
