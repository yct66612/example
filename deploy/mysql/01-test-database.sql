CREATE DATABASE IF NOT EXISTS task_scheduler_test
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON task_scheduler_test.* TO 'scheduler_app'@'%';
FLUSH PRIVILEGES;
