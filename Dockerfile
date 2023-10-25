FROM python:3.11.5

WORKDIR /app

# 复制 requirements.txt 到工作目录
COPY requirements.txt .

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将当前目录下的所有文件复制到工作目录
COPY . .

# 暴露应用程序的端口（Tornado 默认端口为 8888）
EXPOSE 10086

# 定义启动命令
CMD ["python", "server/handler.py"]
