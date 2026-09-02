CREATE DATABASE IF NOT EXISTS task_scheduler CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS task_scheduler_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'scheduler_app'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON task_scheduler.* TO 'scheduler_app'@'localhost';
GRANT ALL PRIVILEGES ON task_scheduler_test.* TO 'scheduler_app'@'localhost';
FLUSH PRIVILEGES;
