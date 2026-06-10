# Nginx 502 Bad Gateway 排查手册

## 现象
客户端收到 HTTP 502 Bad Gateway 错误。

## 常见原因
1. 上游服务（如 PHP-FPM、uWSGI、Gunicorn）未启动或已崩溃
2. 上游服务响应超时（proxy_read_timeout 过短）
3. 上游服务返回了无效响应
4. 网络问题导致 Nginx 无法连接上游

## 排查步骤
1. `systemctl status php-fpm` 确认上游服务状态
2. `tail -f /var/log/nginx/error.log` 查看 Nginx 错误日志
3. `ss -tlnp | grep :9000` 确认上游端口监听
4. `curl -v http://127.0.0.1:9000` 直接测试上游连通性

## 处置方法
1. 重启上游服务：`systemctl restart php-fpm`
2. 调整 Nginx 超时配置：`proxy_read_timeout 60s`
3. 检查上游服务资源限制（max_children、内存等）
4. 临时降级：返回静态维护页面
