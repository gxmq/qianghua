FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY . .

# 创建必要的目录
RUN mkdir -p database logs

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 5001

# 启动命令
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"] 