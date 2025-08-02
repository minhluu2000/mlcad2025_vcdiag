# hash:sha256:efa49b09d05e3f809e846bb8f3bd1e5edb2e87c320096140897379cfa3a0f9ba
FROM registry.codeocean.com/codeocean/miniconda3:4.9.2-cuda11.7.0-cudnn8-ubuntu20.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.8ubuntu1.1 \
        cmake=3.16.3-1ubuntu1.20.04.1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install -U --no-cache-dir \
    jupyter==1.1.1 \
    lightgbm==4.6.0 \
    natsort==8.4.0 \
    numpy==1.24.4 \
    pandas==2.0.3 \
    scipy==1.10.1 \
    seaborn==0.13.2 \
    sktime==0.29.1 \
    tables==3.8.0 \
    tensorflow==2.13.1 \
    torch==2.4.1 \
    xgboost==2.1.4
