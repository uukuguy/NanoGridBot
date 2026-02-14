# NanoGridBot 测试环境配置指南

## 1. 测试环境概述

### 1.1 环境分类

#### 开发环境 (Development)
- **用途**: 开发人员本地开发和调试
- **特点**: 快速迭代，频繁变更
- **数据**: 使用模拟数据或小规模真实数据

#### 测试环境 (Testing)
- **用途**: 执行自动化测试和手动测试
- **特点**: 稳定配置，接近生产环境
- **数据**: 使用完整的测试数据集

#### 预生产环境 (Staging)
- **用途**: 发布前的最终验证
- **特点**: 与生产环境完全一致
- **数据**: 使用生产数据的副本或脱敏数据

#### 生产环境 (Production)
- **用途**: 实际运行环境
- **特点**: 高可用性，严格监控
- **数据**: 真实生产数据

### 1.2 环境隔离

- 每个环境使用独立的配置文件
- 环境间数据完全隔离
- 使用环境变量区分不同环境
- 严格的访问控制和权限管理

## 2. 本地开发环境配置

### 2.1 系统要求

#### 硬件要求
- **CPU**: 2核心或以上
- **内存**: 4GB或以上
- **磁盘**: 10GB可用空间
- **网络**: 稳定的网络连接

#### 软件要求
- **操作系统**: Linux, macOS, 或 Windows 10+
- **Node.js**: 18.x 或更高版本
- **npm**: 9.x 或更高版本
- **Git**: 2.x 或更高版本

### 2.2 环境安装步骤

#### 步骤1: 安装Node.js

**Linux (Ubuntu/Debian)**
```bash
# 使用NodeSource仓库
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 验证安装
node --version
npm --version
```

**macOS**
```bash
# 使用Homebrew
brew install node@20

# 验证安装
node --version
npm --version
```

**Windows**
```powershell
# 下载并安装Node.js安装包
# https://nodejs.org/

# 验证安装
node --version
npm --version
```

#### 步骤2: 克隆项目

```bash
# 克隆仓库
git clone https://github.com/your-org/NanoGridBot.git
cd NanoGridBot

# 切换到开发分支
git checkout dev
```

#### 步骤3: 安装依赖

```bash
# 安装项目依赖
npm install

# 安装开发依赖
npm install --save-dev
```

#### 步骤4: 配置环境变量

创建 `.env.development` 文件：

```bash
# .env.development
NODE_ENV=development
LOG_LEVEL=debug
LOG_DIR=./logs/dev

# 模拟器配置
SIMULATOR_HOST=localhost
SIMULATOR_PORT=8080
SIMULATOR_TIMEOUT=5000

# 控制循环配置
CONTROL_INTERVAL=1000
RETRY_ATTEMPTS=3
RETRY_DELAY=1000

# 数据库配置（如果需要）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nanogridbot_dev
DB_USER=dev_user
DB_PASSWORD=dev_password

# 监控面板配置
MONITOR_PORT=3000
MONITOR_HOST=localhost

# 测试配置
TEST_DATA_DIR=./test-data
TEST_TIMEOUT=10000
```

#### 步骤5: 初始化数据库（如果需要）

```bash
# 创建数据库
npm run db:create

# 运行迁移
npm run db:migrate

# 填充测试数据
npm run db:seed
```

#### 步骤6: 启动模拟器

```bash
# 启动电网模拟器
npm run simulator:start

# 或者在后台运行
npm run simulator:start:bg
```

#### 步骤7: 验证环境

```bash
# 运行健康检查
npm run health-check

# 运行测试
npm test

# 启动开发服务器
npm run dev
```

### 2.3 开发工具配置

#### VSCode配置

创建 `.vscode/settings.json`：

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "eslint.validate": [
    "javascript",
    "javascriptreact"
  ],
  "jest.autoRun": {
    "watch": true,
    "onStartup": ["all-tests"]
  },
  "jest.showCoverageOnLoad": true
}
```

创建 `.vscode/launch.json`：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Run NanoGridBot",
      "program": "${workspaceFolder}/src/index.js",
      "env": {
        "NODE_ENV": "development"
      }
    },
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Tests",
      "program": "${workspaceFolder}/node_modules/.bin/jest",
      "args": [
        "--runInBand",
        "--no-cache"
      ],
      "console": "integratedTerminal",
      "internalConsoleOptions": "neverOpen"
    }
  ]
}
```

#### ESLint配置

`.eslintrc.js` 已在项目中配置，确保编辑器已安装ESLint插件。

#### Git Hooks配置

使用Husky配置Git hooks：

```bash
# 安装Husky
npm install --save-dev husky

# 初始化Husky
npx husky install

# 添加pre-commit hook
npx husky add .husky/pre-commit "npm run lint && npm test"

# 添加commit-msg hook
npx husky add .husky/commit-msg "npx commitlint --edit $1"
```

## 3. 测试环境配置

### 3.1 Docker环境配置

#### Dockerfile.test

```dockerfile
FROM node:20-alpine

# 设置工作目录
WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm ci --only=production && \
    npm cache clean --force

# 复制源代码
COPY . .

# 设置环境变量
ENV NODE_ENV=test
ENV LOG_LEVEL=info

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node healthcheck.js || exit 1

# 启动命令
CMD ["npm", "test"]
```

#### docker-compose.test.yml

```yaml
version: '3.8'

services:
  nanogridbot-test:
    build:
      context: .
      dockerfile: Dockerfile.test
    container_name: nanogridbot-test
    environment:
      - NODE_ENV=test
      - LOG_LEVEL=info
      - SIMULATOR_HOST=simulator
      - SIMULATOR_PORT=8080
    volumes:
      - ./test-results:/app/test-results
      - ./coverage:/app/coverage
    depends_on:
      - simulator
      - postgres
    networks:
      - test-network

  simulator:
    image: nanogrid-simulator:latest
    container_name: grid-simulator-test
    ports:
      - "8080:8080"
    environment:
      - MODE=test
      - DATA_RATE=fast
    networks:
      - test-network

  postgres:
    image: postgres:15-alpine
    container_name: postgres-test
    environment:
      - POSTGRES_DB=nanogridbot_test
      - POSTGRES_USER=test_user
      - POSTGRES_PASSWORD=test_password
    ports:
      - "5432:5432"
    volumes:
      - postgres-test-data:/var/lib/postgresql/data
    networks:
      - test-network

networks:
  test-network:
    driver: bridge

volumes:
  postgres-test-data:
```

### 3.2 启动测试环境

```bash
# 构建测试镜像
docker-compose -f docker-compose.test.yml build

# 启动测试环境
docker-compose -f docker-compose.test.yml up -d

# 查看日志
docker-compose -f docker-compose.test.yml logs -f

# 运行测试
docker-compose -f docker-compose.test.yml exec nanogridbot-test npm test

# 停止测试环境
docker-compose -f docker-compose.test.yml down

# 清理测试数据
docker-compose -f docker-compose.test.yml down -v
```

### 3.3 测试环境配置文件

#### .env.test

```bash
# .env.test
NODE_ENV=test
LOG_LEVEL=info
LOG_DIR=./logs/test

# 模拟器配置
SIMULATOR_HOST=simulator
SIMULATOR_PORT=8080
SIMULATOR_TIMEOUT=5000

# 控制循环配置
CONTROL_INTERVAL=1000
RETRY_ATTEMPTS=3
RETRY_DELAY=1000

# 数据库配置
DB_HOST=postgres
DB_PORT=5432
DB_NAME=nanogridbot_test
DB_USER=test_user
DB_PASSWORD=test_password

# 监控面板配置
MONITOR_PORT=3000
MONITOR_HOST=0.0.0.0

# 测试配置
TEST_DATA_DIR=./test-data
TEST_TIMEOUT=10000
COVERAGE_THRESHOLD=80
```

## 4. CI/CD环境配置

### 4.1 GitHub Actions环境

#### 环境变量配置

在GitHub仓库设置中配置以下Secrets：

- `CODECOV_TOKEN`: Codecov上传令牌
- `DOCKER_USERNAME`: Docker Hub用户名
- `DOCKER_PASSWORD`: Docker Hub密码
- `SLACK_WEBHOOK`: Slack通知webhook（可选）

#### 环境配置文件

`.github/workflows/test.yml` 已在AUTOMATION.md中配置。

### 4.2 Jenkins环境配置

#### Jenkinsfile

```groovy
pipeline {
    agent {
        docker {
            image 'node:20-alpine'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }

    environment {
        NODE_ENV = 'test'
        LOG_LEVEL = 'info'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'npm ci'
            }
        }

        stage('Lint') {
            steps {
                sh 'npm run lint'
            }
        }

        stage('Unit Tests') {
            steps {
                sh 'npm run test:unit'
            }
        }

        stage('Integration Tests') {
            steps {
                sh 'npm run test:integration'
            }
        }

        stage('Coverage') {
            steps {
                sh 'npm run test:coverage'
            }
            post {
                always {
                    publishHTML([
                        reportDir: 'coverage',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        stage('Performance Tests') {
            when {
                branch 'main'
            }
            steps {
                sh 'npm run test:performance'
            }
        }

        stage('Build Docker Image') {
            when {
                branch 'main'
            }
            steps {
                sh 'docker build -t nanogridbot:${BUILD_NUMBER} .'
            }
        }
    }

    post {
        always {
            junit 'test-results/**/*.xml'
            cleanWs()
        }
        success {
            slackSend(
                color: 'good',
                message: "Build Successful: ${env.JOB_NAME} ${env.BUILD_NUMBER}"
            )
        }
        failure {
            slackSend(
                color: 'danger',
                message: "Build Failed: ${env.JOB_NAME} ${env.BUILD_NUMBER}"
            )
        }
    }
}
```

## 5. 模拟器配置

### 5.1 电网模拟器安装

```bash
# 克隆模拟器仓库
git clone https://github.com/your-org/grid-simulator.git
cd grid-simulator

# 安装依赖
npm install

# 配置模拟器
cp config.example.json config.json
```

### 5.2 模拟器配置文件

#### config.json

```json
{
  "server": {
    "host": "localhost",
    "port": 8080
  },
  "grid": {
    "baseVoltage": 220,
    "baseFrequency": 50,
    "maxLoad": 5000,
    "variability": 0.05
  },
  "simulation": {
    "mode": "realistic",
    "updateInterval": 100,
    "scenarios": [
      {
        "name": "normal",
        "duration": 3600,
        "loadPattern": "stable"
      },
      {
        "name": "peak",
        "duration": 1800,
        "loadPattern": "increasing"
      },
      {
        "name": "fault",
        "duration": 300,
        "loadPattern": "spike"
      }
    ]
  },
  "logging": {
    "level": "info",
    "file": "./logs/simulator.log"
  }
}
```

### 5.3 启动模拟器

```bash
# 开发模式
npm run dev

# 生产模式
npm start

# 使用特定场景
npm start -- --scenario=fault

# 后台运行
nohup npm start > simulator.log 2>&1 &
```

## 6. 数据库配置

### 6.1 PostgreSQL配置

#### 安装PostgreSQL

**Linux (Ubuntu/Debian)**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

**macOS**
```bash
brew install postgresql@15
brew services start postgresql@15
```

#### 创建数据库和用户

```sql
-- 连接到PostgreSQL
psql -U postgres

-- 创建用户
CREATE USER nanogrid_dev WITH PASSWORD 'dev_password';
CREATE USER nanogrid_test WITH PASSWORD 'test_password';

-- 创建数据库
CREATE DATABASE nanogridbot_dev OWNER nanogrid_dev;
CREATE DATABASE nanogridbot_test OWNER nanogrid_test;

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE nanogridbot_dev TO nanogrid_dev;
GRANT ALL PRIVILEGES ON DATABASE nanogridbot_test TO nanogrid_test;
```

### 6.2 数据库迁移

#### 迁移脚本示例

```javascript
// migrations/001_create_tables.js
exports.up = async function(db) {
  await db.schema.createTable('grid_data', (table) => {
    table.increments('id').primary();
    table.timestamp('timestamp').notNullable();
    table.decimal('voltage', 10, 2);
    table.decimal('current', 10, 2);
    table.decimal('power', 10, 2);
    table.decimal('frequency', 10, 2);
    table.decimal('load', 5, 4);
    table.string('status', 50);
    table.timestamps(true, true);
  });

  await db.schema.createTable('decisions', (table) => {
    table.increments('id').primary();
    table.timestamp('timestamp').notNullable();
    table.integer('grid_data_id').references('grid_data.id');
    table.string('decision', 100).notNullable();
    table.text('reason');
    table.timestamps(true, true);
  });

  await db.schema.createTable('commands', (table) => {
    table.increments('id').primary();
    table.timestamp('timestamp').notNullable();
    table.integer('decision_id').references('decisions.id');
    table.string('command', 100).notNullable();
    table.json('parameters');
    table.string('status', 50);
    table.text('result');
    table.timestamps(true, true);
  });
};

exports.down = async function(db) {
  await db.schema.dropTableIfExists('commands');
  await db.schema.dropTableIfExists('decisions');
  await db.schema.dropTableIfExists('grid_data');
};
```

#### 运行迁移

```bash
# 运行所有迁移
npm run db:migrate

# 回滚最后一次迁移
npm run db:migrate:rollback

# 重置数据库
npm run db:migrate:reset
```

## 7. 监控和日志配置

### 7.1 日志配置

#### Winston配置

```javascript
// src/utils/logger.js
const winston = require('winston');
const path = require('path');

const logDir = process.env.LOG_DIR || './logs';
const logLevel = process.env.LOG_LEVEL || 'info';

const logger = winston.createLogger({
  level: logLevel,
  format: winston.format.combine(
    winston.format.timestamp({
      format: 'YYYY-MM-DD HH:mm:ss'
    }),
    winston.format.errors({ stack: true }),
    winston.format.splat(),
    winston.format.json()
  ),
  defaultMeta: { service: 'nanogridbot' },
  transports: [
    // 错误日志
    new winston.transports.File({
      filename: path.join(logDir, 'error.log'),
      level: 'error',
      maxsize: 10485760, // 10MB
      maxFiles: 5
    }),
    // 组合日志
    new winston.transports.File({
      filename: path.join(logDir, 'combined.log'),
      maxsize: 10485760,
      maxFiles: 5
    })
  ]
});

// 开发环境添加控制台输出
if (process.env.NODE_ENV !== 'production') {
  logger.add(new winston.transports.Console({
    format: winston.format.combine(
      winston.format.colorize(),
      winston.format.simple()
    )
  }));
}

module.exports = logger;
```

### 7.2 监控配置

#### Prometheus配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'nanogridbot'
    static_configs:
      - targets: ['localhost:3000']
    metrics_path: '/metrics'
```

#### Grafana仪表板配置

```json
{
  "dashboard": {
    "title": "NanoGridBot Monitoring",
    "panels": [
      {
        "title": "Control Loop Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "control_loop_duration_seconds"
          }
        ]
      },
      {
        "title": "Decision Distribution",
        "type": "pie",
        "targets": [
          {
            "expr": "decision_count_total"
          }
        ]
      },
      {
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "up"
          }
        ]
      }
    ]
  }
}
```

## 8. 故障排查

### 8.1 常见问题

#### 问题1: 依赖安装失败

**症状**: `npm install` 失败

**解决方案**:
```bash
# 清理npm缓存
npm cache clean --force

# 删除node_modules和package-lock.json
rm -rf node_modules package-lock.json

# 重新安装
npm install
```

#### 问题2: 测试超时

**症状**: 测试运行超时

**解决方案**:
```javascript
// 增加测试超时时间
jest.setTimeout(30000);

// 或在jest.config.js中配置
module.exports = {
  testTimeout: 30000
};
```

#### 问题3: 模拟器连接失败

**症状**: 无法连接到模拟器

**解决方案**:
```bash
# 检查模拟器是否运行
curl http://localhost:8080/health

# 检查端口是否被占用
lsof -i :8080

# 重启模拟器
npm run simulator:restart
```

#### 问题4: 数据库连接失败

**症状**: 无法连接到数据库

**解决方案**:
```bash
# 检查PostgreSQL是否运行
sudo systemctl status postgresql

# 检查连接参数
psql -h localhost -U nanogrid_dev -d nanogridbot_dev

# 重启PostgreSQL
sudo systemctl restart postgresql
```

### 8.2 调试技巧

#### 使用Node.js调试器

```bash
# 启动调试模式
node --inspect-brk src/index.js

# 在Chrome中打开
chrome://inspect
```

#### 使用VSCode调试

在VSCode中按F5启动调试，使用之前配置的launch.json。

#### 查看详细日志

```bash
# 设置日志级别为debug
export LOG_LEVEL=debug
npm start

# 实时查看日志
tail -f logs/combined.log
```

## 9. 环境维护

### 9.1 定期维护任务

- 每周更新依赖包
- 每月清理旧日志文件
- 每季度审查环境配置
- 定期备份测试数据

### 9.2 环境清理

```bash
# 清理日志
npm run clean:logs

# 清理测试数据
npm run clean:test-data

# 清理Docker资源
docker system prune -a

# 清理npm缓存
npm cache clean --force
```

### 9.3 环境文档更新

- 记录所有环境变更
- 更新配置文档
- 维护故障排查知识库
- 定期审查和更新文档
