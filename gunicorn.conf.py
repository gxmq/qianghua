import multiprocessing

# 绑定的IP和端口
bind = "0.0.0.0:5001"

# 工作进程数 - 容器环境下建议适当减少
workers = 2

# 工作模式
worker_class = 'sync'

# 最大客户端并发数量
worker_connections = 1000

# 进程名称
proc_name = 'qianghua'

# 进程超时时间
timeout = 30

# 最大请求数
max_requests = 2000
max_requests_jitter = 200

# 日志配置
accesslog = '-'  # 输出到标准输出
errorlog = '-'   # 输出到标准错误
loglevel = 'info'

# 前台运行
daemon = False   # 容器环境下应该前台运行

# 关闭进程文件
pidfile = None   # 容器环境下不需要pid文件 