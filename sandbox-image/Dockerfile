FROM python:3.12-slim

# Libraries the generated analysis code may use. No network access exists at run time.
RUN pip install --no-cache-dir \
    pandas numpy matplotlib seaborn scipy openpyxl \
    scikit-learn statsmodels rapidfuzz xlrd

# Unprivileged user; the backend also forces user 1000:1000, a read-only root filesystem and no network.
RUN useradd -m -u 1000 sandbox
USER 1000:1000
WORKDIR /output
