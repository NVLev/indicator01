FROM python:3.12.3-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    redis-tools \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements_backend.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements_backend.txt

RUN pip install --no-cache-dir \
    absl-py==2.3.1 \
    asttokens==3.0.0 \
    astunparse==1.6.3 \
    attrs==25.3.0 \
    backcall==0.2.0 \
    beautifulsoup4==4.13.5 \
    bleach==6.2.0 \
    certifi==2025.8.3 \
    charset-normalizer==3.4.3 \
    contourpy==1.3.3 \
    cycler==0.12.1 \
    decorator==5.2.1 \
    defusedxml==0.7.1 \
    docopt==0.6.2 \
    executing==2.2.1 \
    fastjsonschema==2.21.2 \
    flatbuffers==25.9.23 \
    fonttools==4.60.0 \
    gast==0.6.0 \
    google-pasta==0.2.0 \
    grpcio==1.75.0 \
    h5py==3.14.0 \
    humanize==4.13.0 \
    ipython==8.12.3 \
    jedi==0.19.2 \
    Jinja2==3.1.6 \
    joblib==1.5.2 \
    jsonschema==4.25.1 \
    jsonschema-specifications==2025.9.1 \
    jupyter_client==8.6.3 \
    jupyter_core==5.8.1 \
    jupyterlab_pygments==0.3.0 \
    keras==3.11.3 \
    kiwisolver==1.4.9 \
    libclang==18.1.1 \
    Markdown==3.9 \
    markdown-it-py==4.0.0 \
    matplotlib-inline==0.1.7 \
    mdurl==0.1.2 \
    mistune==3.1.4 \
    ml_dtypes==0.5.3 \
    namex==0.1.0 \
    nbclient==0.10.2 \
    nbconvert==7.16.6 \
    nbformat==5.10.4 \
    opt_einsum==3.4.0 \
    optree==0.17.0 \
    pandocfilters==1.5.1 \
    parso==0.8.5 \
    pexpect==4.9.0 \
    pickleshare==0.7.5 \
    pillow==11.3.0 \
    pipreqs==0.5.0 \
    platformdirs==4.4.0 \
    prometheus_client==0.23.1 \
    protobuf==6.32.1 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.3 \
    Pygments==2.19.2 \
    pyparsing==3.2.5 \
    pyzmq==27.1.0 \
    referencing==0.36.2 \
    requests==2.32.5 \
    rich==14.1.0 \
    rpds-py==0.27.1 \
    scikit-learn==1.7.2 \
    scipy==1.16.2 \
    setuptools==80.9.0 \
    simpleitk==2.5.2 \
    soupsieve==2.8 \
    stack-data==0.6.3 \
    tensorboard==2.20.0 \
    tensorboard-data-server==0.7.2 \
    termcolor==3.1.0 \
    threadpoolctl==3.6.0 \
    tinycss2==1.4.0 \
    tornado==6.5.2 \
    traitlets==5.14.3 \
    urllib3==2.5.0 \
    webencodings==0.5.1 \
    Werkzeug==3.1.3 \
    wheel==0.45.1 \
    wrapt==1.17.3 \
    yarg==0.1.9

# Копируем весь бэкенд в /app/backend
COPY backend /app/backend

ENV PYTHONPATH=/app/backend

RUN mkdir -p /app/uploads /app/processed_studies

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]