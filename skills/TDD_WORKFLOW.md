# TDD 测试驱动开发流程

## 原则

**TDD 三定律：**
1. **先写测试** - 在写任何功能代码之前，先写一个失败的测试
2. **让测试通过** - 只写足够的代码让测试通过
3. **重构** - 在测试通过的前提下，优化代码结构

## 本项目的 TDD 实践

### 技能 A: trade-analyzer

```
测试文件: test_analyzer.py (先写)
├── TestTradeAnalyzer (单元测试)
│   ├── test_load_config_default      ✅ 通过
│   ├── test_load_config_custom       ✅ 通过
│   ├── test_calculate_sharpe_ratio   ✅ 通过
│   ├── test_calculate_max_drawdown   ✅ 通过
│   └── ...
└── TestTradeAnalyzerIntegration (集成测试)
    ├── test_analyze_sample_data      ✅ 通过
    └── test_daily_aggregation        ✅ 通过

实现文件: analyzer.py (后写)
```

### 技能 C: social-harvester

```
测试文件: test_harvester.py (先写)
├── TestMoltbookHarvester
│   ├── test_load_config_default      ✅ 通过
│   ├── test_filter_by_likes          ✅ 通过
│   ├── test_is_duplicate             ✅ 通过
│   └── ...
├── TestContentParser
│   ├── test_extract_code_blocks      ✅ 通过
│   ├── test_extract_hashtags         ✅ 通过
│   ├── test_detect_sentiment         ✅ 通过
│   └── ...
└── TestIntegration
    └── test_harvester_parser_workflow ✅ 通过

实现文件: harvester.py, parser.py (后写)
```

## 运行测试

```bash
# 运行所有测试
cd /home/ubuntu/clawd/skills/trade-analyzer
python3 test_analyzer.py

cd /home/ubuntu/clawd/skills/social-harvester
python3 test_harvester.py

# 运行特定测试
python3 test_analyzer.py TestTradeAnalyzer.test_calculate_win_rate

# 详细输出
python3 test_analyzer.py -v
```

## 测试覆盖率

| 技能 | 测试文件 | 测试类 | 测试方法 | 状态 |
|------|----------|--------|----------|------|
| trade-analyzer | test_analyzer.py | 2 | 12 | ✅ 全部通过 |
| social-harvester | test_harvester.py | 4 | 18 | ✅ 全部通过 |

## 测试金字塔

```
     /\
    /  \  E2E 测试 (端到端)
   /----\
  /      \ 集成测试
 /--------\
/          \ 单元测试 (最多)
------------
```

本项目：
- **单元测试** (80%) - 独立函数、方法
- **集成测试** (15%) - 模块间协作
- **E2E 测试** (5%) - 完整工作流

## 新增功能的 TDD 流程

1. **写测试** → 测试失败 (红色)
2. **写代码** → 测试通过 (绿色)
3. **重构**   → 优化代码 (保持绿色)
4. **提交**   → git commit

## 示例：添加新功能

```python
# Step 1: 先写测试 (test_analyzer.py)
def test_calculate_volatility(self):
    returns = [0.1, -0.05, 0.08, -0.02]
    vol = self.analyzer._calculate_volatility(returns)
    self.assertGreater(vol, 0)

# Step 2: 运行测试 → 失败 (方法不存在)
# python3 test_analyzer.py → FAIL

# Step 3: 实现功能 (analyzer.py)
def _calculate_volatility(self, returns):
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance)

# Step 4: 运行测试 → 通过
# python3 test_analyzer.py → OK

# Step 5: 重构优化 (如有需要)
```

## 持续集成建议

```bash
# 每次提交前运行
./run_tests.sh

# run_tests.sh 内容:
#!/bin/bash
set -e
cd skills/trade-analyzer && python3 test_analyzer.py
cd ../social-harvester && python3 test_harvester.py
echo "All tests passed!"
```
