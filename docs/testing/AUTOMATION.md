# NanoGridBot 自动化测试指南

## 1. 自动化测试概述

### 1.1 自动化测试目标

- 提高测试效率和覆盖率
- 减少人工测试的工作量
- 实现持续集成和持续部署
- 快速发现和定位问题
- 保证代码质量和稳定性

### 1.2 自动化测试范围

#### 适合自动化的测试
- 单元测试
- 集成测试
- API测试
- 回归测试
- 性能测试
- 冒烟测试

#### 不适合自动化的测试
- 探索性测试
- 用户体验测试
- 一次性测试
- 需要人工判断的测试

### 1.3 自动化测试工具栈

- **测试框架**: Jest
- **断言库**: Jest (内置)
- **Mock工具**: Jest (内置)
- **覆盖率工具**: Istanbul (Jest集成)
- **API测试**: Supertest
- **性能测试**: Artillery
- **E2E测试**: Playwright (可选)
- **CI/CD**: GitHub Actions

## 2. 测试框架配置

### 2.1 Jest配置

#### jest.config.js
```javascript
module.exports = {
  // 测试环境
  testEnvironment: 'node',

  // 测试文件匹配模式
  testMatch: [
    '**/__tests__/**/*.js',
    '**/?(*.)+(spec|test).js'
  ],

  // 覆盖率收集
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],

  // 覆盖率阈值
  coverageThreshold: {
    global: {
      branches: 75,
      functions: 85,
      lines: 80,
      statements: 80
    }
  },

  // 需要收集覆盖率的文件
  collectCoverageFrom: [
    'src/**/*.js',
    '!src/**/*.test.js',
    '!src/**/*.spec.js',
    '!src/index.js'
  ],

  // 测试超时时间
  testTimeout: 10000,

  // 设置文件
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],

  // 模块路径映射
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@tests/(.*)$': '<rootDir>/tests/$1'
  },

  // 清除mock
  clearMocks: true,
  resetMocks: true,
  restoreMocks: true,

  // 详细输出
  verbose: true
};
```

### 2.2 测试设置文件

#### tests/setup.js
```javascript
// 全局测试设置
const path = require('path');
const fs = require('fs');

// 设置测试环境变量
process.env.NODE_ENV = 'test';
process.env.LOG_LEVEL = 'error';

// 创建测试目录
const testDirs = [
  path.join(__dirname, '../logs/test'),
  path.join(__dirname, '../data/test')
];

testDirs.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// 全局测试钩子
beforeAll(() => {
  console.log('Starting test suite...');
});

afterAll(() => {
  console.log('Test suite completed.');
  // 清理测试数据
  testDirs.forEach(dir => {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

// 全局错误处理
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});
```

## 3. 单元测试自动化

### 3.1 测试文件组织

```
tests/
├── unit/
│   ├── config/
│   │   └── ConfigManager.test.js
│   ├── data/
│   │   └── DataCollector.test.js
│   ├── decision/
│   │   └── DecisionEngine.test.js
│   ├── executor/
│   │   └── Executor.test.js
│   └── logger/
│       └── Logger.test.js
├── integration/
│   ├── control-loop.test.js
│   └── module-interaction.test.js
├── e2e/
│   └── full-system.test.js
├── fixtures/
│   ├── test-data.js
│   └── mock-data.js
├── helpers/
│   ├── test-utils.js
│   └── mock-factory.js
└── setup.js
```

### 3.2 单元测试示例

#### tests/unit/config/ConfigManager.test.js
```javascript
const ConfigManager = require('@/config/ConfigManager');
const fs = require('fs');
const path = require('path');

describe('ConfigManager', () => {
  let configManager;
  let testConfigPath;

  beforeEach(() => {
    testConfigPath = path.join(__dirname, '../../fixtures/test-config.json');
    configManager = new ConfigManager(testConfigPath);
  });

  afterEach(() => {
    // 清理测试文件
    if (fs.existsSync(testConfigPath)) {
      fs.unlinkSync(testConfigPath);
    }
  });

  describe('loadConfig', () => {
    test('should load default config when file does not exist', () => {
      const config = configManager.loadConfig();

      expect(config).toBeDefined();
      expect(config.grid).toBeDefined();
      expect(config.control).toBeDefined();
      expect(config.logging).toBeDefined();
    });

    test('should load custom config from file', () => {
      const customConfig = {
        grid: {
          voltageMin: 200,
          voltageMax: 240
        }
      };

      fs.writeFileSync(testConfigPath, JSON.stringify(customConfig));
      const config = configManager.loadConfig();

      expect(config.grid.voltageMin).toBe(200);
      expect(config.grid.voltageMax).toBe(240);
    });

    test('should throw error for invalid config', () => {
      const invalidConfig = {
        grid: {
          voltageMin: 250,
          voltageMax: 200 // 无效：最小值大于最大值
        }
      };

      fs.writeFileSync(testConfigPath, JSON.stringify(invalidConfig));

      expect(() => {
        configManager.loadConfig();
      }).toThrow('Invalid configuration');
    });
  });

  describe('validateConfig', () => {
    test('should validate correct config', () => {
      const validConfig = {
        grid: {
          voltageMin: 198,
          voltageMax: 242,
          frequencyMin: 49.5,
          frequencyMax: 50.5,
          loadThreshold: 0.9
        }
      };

      expect(() => {
        configManager.validateConfig(validConfig);
      }).not.toThrow();
    });

    test('should reject config with missing required fields', () => {
      const incompleteConfig = {
        grid: {
          voltageMin: 198
          // 缺少其他必需字段
        }
      };

      expect(() => {
        configManager.validateConfig(incompleteConfig);
      }).toThrow('Missing required field');
    });

    test('should reject config with invalid value ranges', () => {
      const invalidConfig = {
        grid: {
          voltageMin: 250,
          voltageMax: 200,
          frequencyMin: 49.5,
          frequencyMax: 50.5,
          loadThreshold: 0.9
        }
      };

      expect(() => {
        configManager.validateConfig(invalidConfig);
      }).toThrow('Invalid value range');
    });
  });
});
```

#### tests/unit/data/DataCollector.test.js
```javascript
const DataCollector = require('@/data/DataCollector');
const { mockSimulator } = require('@tests/helpers/mock-factory');

describe('DataCollector', () => {
  let dataCollector;
  let simulator;

  beforeEach(() => {
    simulator = mockSimulator();
    dataCollector = new DataCollector(simulator);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('collectData', () => {
    test('should collect valid grid data', async () => {
      const mockData = {
        voltage: 220,
        current: 10,
        power: 2200,
        frequency: 50,
        load: 0.7
      };

      simulator.getData.mockResolvedValue(mockData);

      const data = await dataCollector.collectData();

      expect(data).toEqual(mockData);
      expect(simulator.getData).toHaveBeenCalledTimes(1);
    });

    test('should throw error on timeout', async () => {
      simulator.getData.mockImplementation(() => {
        return new Promise((resolve) => {
          setTimeout(() => resolve({}), 5000);
        });
      });

      dataCollector.setTimeout(1000);

      await expect(dataCollector.collectData()).rejects.toThrow('Timeout');
    });

    test('should validate collected data format', async () => {
      const invalidData = {
        voltage: 220,
        current: 'invalid'
        // 缺少其他字段
      };

      simulator.getData.mockResolvedValue(invalidData);

      await expect(dataCollector.collectData()).rejects.toThrow('Invalid data format');
    });

    test('should retry on failure', async () => {
      simulator.getData
        .mockRejectedValueOnce(new Error('Connection failed'))
        .mockResolvedValueOnce({
          voltage: 220,
          current: 10,
          power: 2200,
          frequency: 50,
          load: 0.7
        });

      dataCollector.setRetryAttempts(2);

      const data = await dataCollector.collectData();

      expect(data).toBeDefined();
      expect(simulator.getData).toHaveBeenCalledTimes(2);
    });
  });

  describe('validateData', () => {
    test('should accept valid data', () => {
      const validData = {
        voltage: 220,
        current: 10,
        power: 2200,
        frequency: 50,
        load: 0.7
      };

      expect(() => {
        dataCollector.validateData(validData);
      }).not.toThrow();
    });

    test('should reject data with missing fields', () => {
      const incompleteData = {
        voltage: 220,
        current: 10
      };

      expect(() => {
        dataCollector.validateData(incompleteData);
      }).toThrow('Missing required field');
    });

    test('should reject data with invalid types', () => {
      const invalidData = {
        voltage: '220',
        current: 10,
        power: 2200,
        frequency: 50,
        load: 0.7
      };

      expect(() => {
        dataCollector.validateData(invalidData);
      }).toThrow('Invalid data type');
    });
  });
});
```

### 3.3 测试辅助工具

#### tests/helpers/mock-factory.js
```javascript
// Mock工厂函数
function mockSimulator() {
  return {
    getData: jest.fn(),
    sendCommand: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    isConnected: jest.fn().mockReturnValue(true)
  };
}

function mockLogger() {
  return {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn()
  };
}

function mockConfigManager() {
  return {
    loadConfig: jest.fn().mockReturnValue({
      grid: {
        voltageMin: 198,
        voltageMax: 242,
        frequencyMin: 49.5,
        frequencyMax: 50.5,
        loadThreshold: 0.9
      },
      control: {
        interval: 1000,
        retryAttempts: 3,
        retryDelay: 1000
      }
    }),
    validateConfig: jest.fn(),
    getConfig: jest.fn()
  };
}

module.exports = {
  mockSimulator,
  mockLogger,
  mockConfigManager
};
```

#### tests/helpers/test-utils.js
```javascript
// 测试工具函数
function waitFor(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function generateTestData(overrides = {}) {
  return {
    voltage: 220,
    current: 10,
    power: 2200,
    frequency: 50,
    load: 0.7,
    powerFactor: 0.95,
    temperature: 25,
    humidity: 60,
    ...overrides
  };
}

function expectToBeWithinRange(value, min, max) {
  expect(value).toBeGreaterThanOrEqual(min);
  expect(value).toBeLessThanOrEqual(max);
}

async function expectAsyncError(asyncFn, errorMessage) {
  await expect(asyncFn()).rejects.toThrow(errorMessage);
}

module.exports = {
  waitFor,
  generateTestData,
  expectToBeWithinRange,
  expectAsyncError
};
```

## 4. 集成测试自动化

### 4.1 集成测试示例

#### tests/integration/control-loop.test.js
```javascript
const NanoGridBot = require('@/NanoGridBot');
const { mockSimulator } = require('@tests/helpers/mock-factory');
const { waitFor, generateTestData } = require('@tests/helpers/test-utils');

describe('Control Loop Integration', () => {
  let bot;
  let simulator;

  beforeEach(() => {
    simulator = mockSimulator();
    bot = new NanoGridBot({ simulator });
  });

  afterEach(async () => {
    await bot.stop();
  });

  test('should execute complete control loop', async () => {
    const testData = generateTestData();
    simulator.getData.mockResolvedValue(testData);
    simulator.sendCommand.mockResolvedValue({ success: true });

    await bot.start();
    await waitFor(1500); // 等待一个控制周期

    expect(simulator.getData).toHaveBeenCalled();
    expect(simulator.sendCommand).toHaveBeenCalled();
  });

  test('should handle data collection failure', async () => {
    simulator.getData.mockRejectedValue(new Error('Connection failed'));

    await bot.start();
    await waitFor(1500);

    // 验证错误被正确处理
    const logs = bot.getLogger().getLogs();
    expect(logs).toContainEqual(
      expect.objectContaining({
        level: 'error',
        message: expect.stringContaining('Connection failed')
      })
    );
  });

  test('should make correct decision based on data', async () => {
    const overloadData = generateTestData({ load: 0.95 });
    simulator.getData.mockResolvedValue(overloadData);
    simulator.sendCommand.mockResolvedValue({ success: true });

    await bot.start();
    await waitFor(1500);

    expect(simulator.sendCommand).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'reduce_load'
      })
    );
  });
});
```

## 5. 性能测试自动化

### 5.1 Artillery配置

#### artillery.yml
```yaml
config:
  target: 'http://localhost:3000'
  phases:
    - duration: 60
      arrivalRate: 10
      name: "Warm up"
    - duration: 120
      arrivalRate: 50
      name: "Sustained load"
    - duration: 60
      arrivalRate: 100
      name: "Peak load"
  plugins:
    expect: {}
  processor: "./tests/performance/processor.js"

scenarios:
  - name: "Control Loop Performance"
    flow:
      - get:
          url: "/api/status"
          expect:
            - statusCode: 200
            - contentType: json
            - hasProperty: "status"
      - think: 1
      - post:
          url: "/api/control"
          json:
            voltage: 220
            current: 10
            power: 2200
            frequency: 50
            load: 0.7
          expect:
            - statusCode: 200
            - hasProperty: "decision"
      - think: 1
```

### 5.2 性能测试脚本

#### tests/performance/control-loop-perf.test.js
```javascript
const { performance } = require('perf_hooks');
const DecisionEngine = require('@/decision/DecisionEngine');
const { generateTestData } = require('@tests/helpers/test-utils');

describe('Performance Tests', () => {
  let decisionEngine;

  beforeEach(() => {
    decisionEngine = new DecisionEngine();
  });

  test('should process 1000 decisions within 1 second', () => {
    const testData = Array(1000).fill(null).map(() => generateTestData());

    const startTime = performance.now();

    testData.forEach(data => {
      decisionEngine.makeDecision(data);
    });

    const endTime = performance.now();
    const duration = endTime - startTime;

    expect(duration).toBeLessThan(1000);
    console.log(`Processed 1000 decisions in ${duration.toFixed(2)}ms`);
  });

  test('should maintain consistent performance under load', () => {
    const iterations = 100;
    const durations = [];

    for (let i = 0; i < iterations; i++) {
      const testData = generateTestData();
      const startTime = performance.now();

      decisionEngine.makeDecision(testData);

      const endTime = performance.now();
      durations.push(endTime - startTime);
    }

    const avgDuration = durations.reduce((a, b) => a + b) / durations.length;
    const maxDuration = Math.max(...durations);

    expect(avgDuration).toBeLessThan(1);
    expect(maxDuration).toBeLessThan(5);

    console.log(`Average: ${avgDuration.toFixed(2)}ms, Max: ${maxDuration.toFixed(2)}ms`);
  });

  test('should not have memory leaks', () => {
    const initialMemory = process.memoryUsage().heapUsed;

    // 执行大量操作
    for (let i = 0; i < 10000; i++) {
      const testData = generateTestData();
      decisionEngine.makeDecision(testData);
    }

    // 强制垃圾回收（需要 --expose-gc 标志）
    if (global.gc) {
      global.gc();
    }

    const finalMemory = process.memoryUsage().heapUsed;
    const memoryIncrease = finalMemory - initialMemory;

    // 内存增长应该在合理范围内（例如小于10MB）
    expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024);

    console.log(`Memory increase: ${(memoryIncrease / 1024 / 1024).toFixed(2)}MB`);
  });
});
```

## 6. CI/CD集成

### 6.1 GitHub Actions配置

#### .github/workflows/test.yml
```yaml
name: Test

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main, dev ]

jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        node-version: [18.x, 20.x]

    steps:
    - uses: actions/checkout@v3

    - name: Use Node.js ${{ matrix.node-version }}
      uses: actions/setup-node@v3
      with:
        node-version: ${{ matrix.node-version }}
        cache: 'npm'

    - name: Install dependencies
      run: npm ci

    - name: Run linter
      run: npm run lint

    - name: Run unit tests
      run: npm run test:unit

    - name: Run integration tests
      run: npm run test:integration

    - name: Run coverage
      run: npm run test:coverage

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage/lcov.info
        flags: unittests
        name: codecov-umbrella

    - name: Check coverage thresholds
      run: npm run test:coverage:check

  performance:
    runs-on: ubuntu-latest
    needs: test

    steps:
    - uses: actions/checkout@v3

    - name: Use Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '20.x'

    - name: Install dependencies
      run: npm ci

    - name: Run performance tests
      run: npm run test:performance

    - name: Upload performance results
      uses: actions/upload-artifact@v3
      with:
        name: performance-results
        path: ./performance-results/
```

### 6.2 NPM脚本配置

#### package.json
```json
{
  "scripts": {
    "test": "jest",
    "test:unit": "jest --testPathPattern=tests/unit",
    "test:integration": "jest --testPathPattern=tests/integration",
    "test:e2e": "jest --testPathPattern=tests/e2e",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:coverage:check": "jest --coverage --coverageThreshold='{\"global\":{\"branches\":75,\"functions\":85,\"lines\":80,\"statements\":80}}'",
    "test:performance": "node tests/performance/run-all.js",
    "test:debug": "node --inspect-brk node_modules/.bin/jest --runInBand",
    "lint": "eslint src tests",
    "lint:fix": "eslint src tests --fix"
  }
}
```

## 7. 测试报告

### 7.1 生成HTML报告

#### jest.config.js (添加报告配置)
```javascript
module.exports = {
  // ... 其他配置
  reporters: [
    'default',
    [
      'jest-html-reporter',
      {
        pageTitle: 'NanoGridBot Test Report',
        outputPath: 'test-report/index.html',
        includeFailureMsg: true,
        includeConsoleLog: true,
        theme: 'darkTheme',
        sort: 'status'
      }
    ]
  ]
};
```

### 7.2 自定义报告生成器

#### tests/reporters/custom-reporter.js
```javascript
class CustomReporter {
  constructor(globalConfig, options) {
    this._globalConfig = globalConfig;
    this._options = options;
  }

  onRunComplete(contexts, results) {
    const summary = {
      totalTests: results.numTotalTests,
      passedTests: results.numPassedTests,
      failedTests: results.numFailedTests,
      pendingTests: results.numPendingTests,
      duration: results.testResults.reduce((acc, result) => {
        return acc + (result.perfStats.end - result.perfStats.start);
      }, 0),
      coverage: results.coverageMap ? {
        statements: results.coverageMap.getCoverageSummary().statements.pct,
        branches: results.coverageMap.getCoverageSummary().branches.pct,
        functions: results.coverageMap.getCoverageSummary().functions.pct,
        lines: results.coverageMap.getCoverageSummary().lines.pct
      } : null
    };

    console.log('\n=== Test Summary ===');
    console.log(`Total: ${summary.totalTests}`);
    console.log(`Passed: ${summary.passedTests}`);
    console.log(`Failed: ${summary.failedTests}`);
    console.log(`Pending: ${summary.pendingTests}`);
    console.log(`Duration: ${(summary.duration / 1000).toFixed(2)}s`);

    if (summary.coverage) {
      console.log('\n=== Coverage ===');
      console.log(`Statements: ${summary.coverage.statements.toFixed(2)}%`);
      console.log(`Branches: ${summary.coverage.branches.toFixed(2)}%`);
      console.log(`Functions: ${summary.coverage.functions.toFixed(2)}%`);
      console.log(`Lines: ${summary.coverage.lines.toFixed(2)}%`);
    }
  }
}

module.exports = CustomReporter;
```

## 8. 最佳实践

### 8.1 测试编写原则

1. **独立性**: 每个测试应该独立运行，不依赖其他测试
2. **可重复性**: 测试结果应该是确定的和可重复的
3. **快速性**: 单元测试应该快速执行
4. **清晰性**: 测试代码应该易于理解
5. **完整性**: 测试应该覆盖正常和异常情况

### 8.2 Mock使用建议

- 只mock外部依赖，不mock被测试的代码
- 使用工厂函数创建mock对象
- 在每个测试后清理mock状态
- 验证mock的调用次数和参数

### 8.3 测试维护

- 定期审查和更新测试用例
- 删除过时或重复的测试
- 保持测试代码的质量
- 及时修复失败的测试

### 8.4 持续改进

- 监控测试覆盖率趋势
- 分析测试执行时间
- 优化慢速测试
- 增加自动化测试的范围
