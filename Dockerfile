FROM python:3.12-slim

# Defina o diretório de trabalho dentro do container
WORKDIR /app

# Copie todo o seu projeto para o diretório de trabalho no container
COPY . .
