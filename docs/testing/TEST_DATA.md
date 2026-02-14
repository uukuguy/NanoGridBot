# NanoGridBot 测试数据管理

## 1. 测试数据概述

### 1.1 测试数据分类

#### 正常数据
用于验证系统在正常工作条件下的行为。

#### 边界数据
用于测试系统在极限条件下的行为。

#### 异常数据
用于验证系统的错误处理和容错能力。

#### 压力数据
用于性能和压力测试。

### 1.2 测试数据来源

- **真实数据**: 从实际电网系统采集的数据
- **模拟数据**: 通过模拟器生成的数据
- **合成数据**: 人工构造的测试数据
- **历史数据**: 过往测试中使用的数据

## 2. 电网数据集

### 2.1 正常运行数据集

#### 数据集1: 标准负载
```json
{
  "datasetId": "NORMAL_001",
  "description": "标准负载条件下的电网数据",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10,
    "power": 2200,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.95,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "maintain",
  "tags": ["normal", "standard", "baseline"]
}
```

#### 数据集2: 低负载
```json
{
  "datasetId": "NORMAL_002",
  "description": "低负载条件下的电网数据",
  "timestamp": "2024-01-01T01:00:00Z",
  "data": {
    "voltage": 220,
    "current": 3,
    "power": 660,
    "frequency": 50,
    "load": 0.2,
    "powerFactor": 0.92,
    "temperature": 23,
    "humidity": 58
  },
  "expectedDecision": "maintain",
  "tags": ["normal", "low-load"]
}
```

#### 数据集3: 高负载
```json
{
  "datasetId": "NORMAL_003",
  "description": "高负载但正常范围内的电网数据",
  "timestamp": "2024-01-01T02:00:00Z",
  "data": {
    "voltage": 220,
    "current": 18,
    "power": 3960,
    "frequency": 50,
    "load": 0.85,
    "powerFactor": 0.96,
    "temperature": 28,
    "humidity": 62
  },
  "expectedDecision": "maintain",
  "tags": ["normal", "high-load"]
}
```

### 2.2 边界数据集

#### 数据集4: 电压下限
```json
{
  "datasetId": "BOUNDARY_001",
  "description": "电压接近下限的数据",
  "timestamp": "2024-01-01T03:00:00Z",
  "data": {
    "voltage": 198,
    "current": 10,
    "power": 1980,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.93,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "adjust_voltage",
  "tags": ["boundary", "voltage-low"]
}
```

#### 数据集5: 电压上限
```json
{
  "datasetId": "BOUNDARY_002",
  "description": "电压接近上限的数据",
  "timestamp": "2024-01-01T04:00:00Z",
  "data": {
    "voltage": 242,
    "current": 10,
    "power": 2420,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.94,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "adjust_voltage",
  "tags": ["boundary", "voltage-high"]
}
```

#### 数据集6: 负载上限
```json
{
  "datasetId": "BOUNDARY_003",
  "description": "负载接近上限的数据",
  "timestamp": "2024-01-01T05:00:00Z",
  "data": {
    "voltage": 220,
    "current": 20,
    "power": 4400,
    "frequency": 50,
    "load": 0.90,
    "powerFactor": 0.97,
    "temperature": 30,
    "humidity": 65
  },
  "expectedDecision": "reduce_load",
  "tags": ["boundary", "load-high"]
}
```

#### 数据集7: 频率下限
```json
{
  "datasetId": "BOUNDARY_004",
  "description": "频率接近下限的数据",
  "timestamp": "2024-01-01T06:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10,
    "power": 2200,
    "frequency": 49.5,
    "load": 0.7,
    "powerFactor": 0.95,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "adjust_frequency",
  "tags": ["boundary", "frequency-low"]
}
```

#### 数据集8: 频率上限
```json
{
  "datasetId": "BOUNDARY_005",
  "description": "频率接近上限的数据",
  "timestamp": "2024-01-01T07:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10,
    "power": 2200,
    "frequency": 50.5,
    "load": 0.7,
    "powerFactor": 0.95,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "adjust_frequency",
  "tags": ["boundary", "frequency-high"]
}
```

### 2.3 异常数据集

#### 数据集9: 过载
```json
{
  "datasetId": "ABNORMAL_001",
  "description": "系统过载的数据",
  "timestamp": "2024-01-01T08:00:00Z",
  "data": {
    "voltage": 220,
    "current": 25,
    "power": 5500,
    "frequency": 50,
    "load": 0.98,
    "powerFactor": 0.98,
    "temperature": 35,
    "humidity": 70
  },
  "expectedDecision": "emergency_shutdown",
  "tags": ["abnormal", "overload", "critical"]
}
```

#### 数据集10: 电压异常高
```json
{
  "datasetId": "ABNORMAL_002",
  "description": "电压异常高的数据",
  "timestamp": "2024-01-01T09:00:00Z",
  "data": {
    "voltage": 250,
    "current": 10,
    "power": 2500,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.93,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "emergency_adjust_voltage",
  "tags": ["abnormal", "voltage-critical", "critical"]
}
```

#### 数据集11: 电压异常低
```json
{
  "datasetId": "ABNORMAL_003",
  "description": "电压异常低的数据",
  "timestamp": "2024-01-01T10:00:00Z",
  "data": {
    "voltage": 190,
    "current": 10,
    "power": 1900,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.92,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "emergency_adjust_voltage",
  "tags": ["abnormal", "voltage-critical", "critical"]
}
```

#### 数据集12: 频率异常
```json
{
  "datasetId": "ABNORMAL_004",
  "description": "频率异常的数据",
  "timestamp": "2024-01-01T11:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10,
    "power": 2200,
    "frequency": 48,
    "load": 0.7,
    "powerFactor": 0.95,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "emergency_adjust_frequency",
  "tags": ["abnormal", "frequency-critical", "critical"]
}
```

#### 数据集13: 功率因数异常
```json
{
  "datasetId": "ABNORMAL_005",
  "description": "功率因数异常低的数据",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10,
    "power": 1800,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.82,
    "temperature": 25,
    "humidity": 60
  },
  "expectedDecision": "adjust_power_factor",
  "tags": ["abnormal", "power-factor-low"]
}
```

#### 数据集14: 温度过高
```json
{
  "datasetId": "ABNORMAL_006",
  "description": "设备温度过高的数据",
  "timestamp": "2024-01-01T13:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10,
    "power": 2200,
    "frequency": 50,
    "load": 0.7,
    "powerFactor": 0.95,
    "temperature": 45,
    "humidity": 60
  },
  "expectedDecision": "reduce_load",
  "tags": ["abnormal", "temperature-high", "warning"]
}
```

### 2.4 压力测试数据集

#### 数据集15: 快速波动
```json
{
  "datasetId": "STRESS_001",
  "description": "负载快速波动的数据序列",
  "timestamp": "2024-01-01T14:00:00Z",
  "dataSequence": [
    {"voltage": 220, "current": 5, "power": 1100, "load": 0.3},
    {"voltage": 220, "current": 15, "power": 3300, "load": 0.8},
    {"voltage": 220, "current": 8, "power": 1760, "load": 0.5},
    {"voltage": 220, "current": 18, "power": 3960, "load": 0.85},
    {"voltage": 220, "current": 10, "power": 2200, "load": 0.7}
  ],
  "interval": "1s",
  "tags": ["stress", "rapid-change"]
}
```

#### 数据集16: 持续高负载
```json
{
  "datasetId": "STRESS_002",
  "description": "持续高负载的数据",
  "timestamp": "2024-01-01T15:00:00Z",
  "duration": "1h",
  "data": {
    "voltage": 220,
    "current": 19,
    "power": 4180,
    "frequency": 50,
    "load": 0.88,
    "powerFactor": 0.97,
    "temperature": 32,
    "humidity": 65
  },
  "tags": ["stress", "sustained-high-load"]
}
```

### 2.5 错误数据集

#### 数据集17: 缺失字段
```json
{
  "datasetId": "ERROR_001",
  "description": "缺失必要字段的数据",
  "timestamp": "2024-01-01T16:00:00Z",
  "data": {
    "voltage": 220,
    "current": 10
    // 缺少 power, frequency, load 等字段
  },
  "expectedBehavior": "throw_validation_error",
  "tags": ["error", "missing-fields"]
}
```

#### 数据集18: 无效数值
```json
{
  "datasetId": "ERROR_002",
  "description": "包含无效数值的数据",
  "timestamp": "2024-01-01T17:00:00Z",
  "data": {
    "voltage": -220,
    "current": "invalid",
    "power": null,
    "frequency": 50,
    "load": 1.5,
    "powerFactor": 0.95,
    "temperature": 25,
    "humidity": 60
  },
  "expectedBehavior": "throw_validation_error",
  "tags": ["error", "invalid-values"]
}
```

#### 数据集19: 格式错误
```json
{
  "datasetId": "ERROR_003",
  "description": "JSON格式错误的数据",
  "timestamp": "2024-01-01T18:00:00Z",
  "rawData": "{voltage: 220, current: 10, power: 2200",
  "expectedBehavior": "throw_parse_error",
  "tags": ["error", "malformed-json"]
}
```

## 3. 配置数据集

### 3.1 有效配置

#### 配置1: 默认配置
```json
{
  "configId": "CONFIG_001",
  "description": "系统默认配置",
  "config": {
    "grid": {
      "voltageMin": 198,
      "voltageMax": 242,
      "frequencyMin": 49.5,
      "frequencyMax": 50.5,
      "loadThreshold": 0.9
    },
    "control": {
      "interval": 1000,
      "retryAttempts": 3,
      "retryDelay": 1000
    },
    "logging": {
      "level": "info",
      "maxSize": "10m",
      "maxFiles": 5
    }
  },
  "tags": ["config", "default", "valid"]
}
```

#### 配置2: 严格模式配置
```json
{
  "configId": "CONFIG_002",
  "description": "严格模式配置，更窄的容差范围",
  "config": {
    "grid": {
      "voltageMin": 210,
      "voltageMax": 230,
      "frequencyMin": 49.8,
      "frequencyMax": 50.2,
      "loadThreshold": 0.85
    },
    "control": {
      "interval": 500,
      "retryAttempts": 5,
      "retryDelay": 500
    },
    "logging": {
      "level": "debug",
      "maxSize": "20m",
      "maxFiles": 10
    }
  },
  "tags": ["config", "strict", "valid"]
}
```

#### 配置3: 宽松模式配置
```json
{
  "configId": "CONFIG_003",
  "description": "宽松模式配置，更宽的容差范围",
  "config": {
    "grid": {
      "voltageMin": 190,
      "voltageMax": 250,
      "frequencyMin": 49,
      "frequencyMax": 51,
      "loadThreshold": 0.95
    },
    "control": {
      "interval": 2000,
      "retryAttempts": 2,
      "retryDelay": 2000
    },
    "logging": {
      "level": "warn",
      "maxSize": "5m",
      "maxFiles": 3
    }
  },
  "tags": ["config", "relaxed", "valid"]
}
```

### 3.2 无效配置

#### 配置4: 缺失必要字段
```json
{
  "configId": "CONFIG_INVALID_001",
  "description": "缺失必要字段的配置",
  "config": {
    "grid": {
      "voltageMin": 198
      // 缺少其他必要字段
    }
  },
  "expectedBehavior": "throw_validation_error",
  "tags": ["config", "invalid", "missing-fields"]
}
```

#### 配置5: 无效数值范围
```json
{
  "configId": "CONFIG_INVALID_002",
  "description": "包含无效数值范围的配置",
  "config": {
    "grid": {
      "voltageMin": 250,
      "voltageMax": 200,
      "frequencyMin": 51,
      "frequencyMax": 49,
      "loadThreshold": 1.5
    },
    "control": {
      "interval": -1000,
      "retryAttempts": 0,
      "retryDelay": -500
    }
  },
  "expectedBehavior": "throw_validation_error",
  "tags": ["config", "invalid", "invalid-range"]
}
```

## 4. 时间序列数据集

### 4.1 日常运行模式
```json
{
  "datasetId": "TIMESERIES_001",
  "description": "24小时日常运行模式数据",
  "startTime": "2024-01-01T00:00:00Z",
  "interval": "1h",
  "data": [
    {"hour": 0, "load": 0.3, "voltage": 220, "frequency": 50},
    {"hour": 1, "load": 0.25, "voltage": 220, "frequency": 50},
    {"hour": 2, "load": 0.22, "voltage": 220, "frequency": 50},
    {"hour": 3, "load": 0.20, "voltage": 220, "frequency": 50},
    {"hour": 4, "load": 0.23, "voltage": 220, "frequency": 50},
    {"hour": 5, "load": 0.28, "voltage": 220, "frequency": 50},
    {"hour": 6, "load": 0.45, "voltage": 220, "frequency": 50},
    {"hour": 7, "load": 0.65, "voltage": 220, "frequency": 50},
    {"hour": 8, "load": 0.75, "voltage": 220, "frequency": 50},
    {"hour": 9, "load": 0.80, "voltage": 220, "frequency": 50},
    {"hour": 10, "load": 0.82, "voltage": 220, "frequency": 50},
    {"hour": 11, "load": 0.85, "voltage": 220, "frequency": 50},
    {"hour": 12, "load": 0.83, "voltage": 220, "frequency": 50},
    {"hour": 13, "load": 0.80, "voltage": 220, "frequency": 50},
    {"hour": 14, "load": 0.78, "voltage": 220, "frequency": 50},
    {"hour": 15, "load": 0.75, "voltage": 220, "frequency": 50},
    {"hour": 16, "load": 0.72, "voltage": 220, "frequency": 50},
    {"hour": 17, "load": 0.70, "voltage": 220, "frequency": 50},
    {"hour": 18, "load": 0.75, "voltage": 220, "frequency": 50},
    {"hour": 19, "load": 0.80, "voltage": 220, "frequency": 50},
    {"hour": 20, "load": 0.78, "voltage": 220, "frequency": 50},
    {"hour": 21, "load": 0.70, "voltage": 220, "frequency": 50},
    {"hour": 22, "load": 0.55, "voltage": 220, "frequency": 50},
    {"hour": 23, "load": 0.40, "voltage": 220, "frequency": 50}
  ],
  "tags": ["timeseries", "daily-pattern"]
}
```

### 4.2 故障恢复场景
```json
{
  "datasetId": "TIMESERIES_002",
  "description": "故障发生和恢复过程的数据",
  "startTime": "2024-01-01T12:00:00Z",
  "interval": "10s",
  "data": [
    {"time": 0, "status": "normal", "load": 0.7, "voltage": 220},
    {"time": 10, "status": "normal", "load": 0.7, "voltage": 220},
    {"time": 20, "status": "fault_detected", "load": 0.95, "voltage": 215},
    {"time": 30, "status": "fault_handling", "load": 0.98, "voltage": 210},
    {"time": 40, "status": "reducing_load", "load": 0.85, "voltage": 215},
    {"time": 50, "status": "stabilizing", "load": 0.75, "voltage": 218},
    {"time": 60, "status": "recovered", "load": 0.70, "voltage": 220},
    {"time": 70, "status": "normal", "load": 0.70, "voltage": 220}
  ],
  "tags": ["timeseries", "fault-recovery"]
}
```

## 5. 测试数据管理

### 5.1 数据存储结构
```
test-data/
├── normal/
│   ├── standard-load.json
│   ├── low-load.json
│   └── high-load.json
├── boundary/
│   ├── voltage-limits.json
│   ├── frequency-limits.json
│   └── load-limits.json
├── abnormal/
│   ├── overload.json
│   ├── voltage-critical.json
│   └── frequency-critical.json
├── stress/
│   ├── rapid-change.json
│   └── sustained-load.json
├── error/
│   ├── missing-fields.json
│   ├── invalid-values.json
│   └── malformed-data.json
├── config/
│   ├── valid-configs.json
│   └── invalid-configs.json
└── timeseries/
    ├── daily-pattern.json
    └── fault-recovery.json
```

### 5.2 数据加载工具

#### 数据加载器示例
```javascript
// test-data/loader.js
const fs = require('fs');
const path = require('path');

class TestDataLoader {
  constructor(dataDir = './test-data') {
    this.dataDir = dataDir;
  }

  loadDataset(category, filename) {
    const filePath = path.join(this.dataDir, category, filename);
    const rawData = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(rawData);
  }

  loadAllDatasets(category) {
    const categoryDir = path.join(this.dataDir, category);
    const files = fs.readdirSync(categoryDir);
    return files.map(file => this.loadDataset(category, file));
  }

  getDatasetById(datasetId) {
    // 实现根据ID查找数据集的逻辑
  }

  getDatasetsByTag(tag) {
    // 实现根据标签查找数据集的逻辑
  }
}

module.exports = TestDataLoader;
```

### 5.3 数据验证规则

#### 电网数据验证
```javascript
const gridDataSchema = {
  voltage: {
    type: 'number',
    min: 0,
    max: 500,
    required: true
  },
  current: {
    type: 'number',
    min: 0,
    max: 100,
    required: true
  },
  power: {
    type: 'number',
    min: 0,
    required: true
  },
  frequency: {
    type: 'number',
    min: 45,
    max: 55,
    required: true
  },
  load: {
    type: 'number',
    min: 0,
    max: 1,
    required: true
  },
  powerFactor: {
    type: 'number',
    min: 0,
    max: 1,
    required: false
  },
  temperature: {
    type: 'number',
    min: -50,
    max: 100,
    required: false
  },
  humidity: {
    type: 'number',
    min: 0,
    max: 100,
    required: false
  }
};
```

### 5.4 数据生成工具

#### 随机数据生成器
```javascript
class TestDataGenerator {
  generateNormalData(count = 100) {
    const data = [];
    for (let i = 0; i < count; i++) {
      data.push({
        voltage: this.randomInRange(210, 230),
        current: this.randomInRange(5, 15),
        power: this.randomInRange(1000, 3500),
        frequency: this.randomInRange(49.8, 50.2),
        load: this.randomInRange(0.5, 0.8),
        powerFactor: this.randomInRange(0.9, 0.98),
        temperature: this.randomInRange(20, 30),
        humidity: this.randomInRange(50, 70)
      });
    }
    return data;
  }

  generateBoundaryData() {
    // 生成边界数据的逻辑
  }

  generateAbnormalData() {
    // 生成异常数据的逻辑
  }

  randomInRange(min, max) {
    return min + Math.random() * (max - min);
  }
}
```

## 6. 数据使用指南

### 6.1 单元测试中使用测试数据

```javascript
const TestDataLoader = require('./test-data/loader');
const loader = new TestDataLoader();

describe('DecisionEngine', () => {
  test('should maintain on normal data', () => {
    const testData = loader.loadDataset('normal', 'standard-load.json');
    const decision = decisionEngine.makeDecision(testData.data);
    expect(decision).toBe(testData.expectedDecision);
  });

  test('should adjust voltage on boundary data', () => {
    const testData = loader.loadDataset('boundary', 'voltage-limits.json');
    const decision = decisionEngine.makeDecision(testData.data);
    expect(decision).toBe(testData.expectedDecision);
  });
});
```

### 6.2 集成测试中使用测试数据

```javascript
describe('End-to-End Flow', () => {
  test('should handle complete control loop', async () => {
    const testData = loader.loadDataset('normal', 'standard-load.json');

    // 模拟数据采集
    mockDataCollector.setData(testData.data);

    // 执行控制循环
    await nanoGridBot.runControlLoop();

    // 验证结果
    expect(mockExecutor.lastCommand).toBe(testData.expectedDecision);
  });
});
```

### 6.3 性能测试中使用测试数据

```javascript
describe('Performance Test', () => {
  test('should process 1000 data points within time limit', async () => {
    const testData = generator.generateNormalData(1000);

    const startTime = Date.now();
    for (const data of testData) {
      await decisionEngine.makeDecision(data);
    }
    const endTime = Date.now();

    const duration = endTime - startTime;
    expect(duration).toBeLessThan(1000); // 应在1秒内完成
  });
});
```

## 7. 数据维护

### 7.1 数据更新流程
1. 识别需要更新的数据集
2. 创建新版本的数据文件
3. 更新数据集文档
4. 运行相关测试验证
5. 提交代码审查
6. 合并到主分支

### 7.2 数据版本控制
- 所有测试数据文件纳入Git版本控制
- 使用语义化版本号标记数据集版本
- 保留历史版本以支持回归测试

### 7.3 数据质量检查
- 定期审查测试数据的有效性
- 验证数据是否符合最新的业务规则
- 检查数据覆盖率是否充分

## 8. 最佳实践

### 8.1 数据设计原则
- **真实性**: 测试数据应尽可能接近真实场景
- **完整性**: 覆盖所有可能的数据状态
- **可维护性**: 数据结构清晰，易于理解和修改
- **可重用性**: 数据可在多个测试中重用

### 8.2 数据使用建议
- 使用数据加载器统一管理测试数据
- 避免在测试代码中硬编码测试数据
- 为每个测试场景准备专门的数据集
- 定期清理和更新过时的测试数据

### 8.3 数据安全
- 不在测试数据中包含真实的敏感信息
- 使用脱敏数据进行测试
- 限制测试数据的访问权限
