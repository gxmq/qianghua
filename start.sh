#!/bin/bash

# 创建必要的目录
mkdir -p logs
mkdir -p database

case "$1" in
    start)
        echo "Starting qianghua application..."
        gunicorn -c gunicorn.conf.py app:app
        ;;
    stop)
        echo "Stopping qianghua application..."
        if [ -f logs/gunicorn.pid ]; then
            kill -TERM $(cat logs/gunicorn.pid)
            rm -f logs/gunicorn.pid
        else
            echo "Application is not running"
        fi
        ;;
    restart)
        echo "Restarting qianghua application..."
        if [ -f logs/gunicorn.pid ]; then
            kill -TERM $(cat logs/gunicorn.pid)
            rm -f logs/gunicorn.pid
        fi
        sleep 2
        gunicorn -c gunicorn.conf.py app:app
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac

exit 0 