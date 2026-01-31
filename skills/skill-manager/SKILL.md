# skill-manager

> Centralized Skill Management for AI Agents

Version: 0.1.0 | Built with TDD principles

## What It Does

Manages all your agent skills in one place:
- **Register** new skills with validation
- **Health check** skills with checksum verification
- **Backup** skills before updates
- **Track** dependencies between skills

## Installation

```bash
cp skill_manager.py ~/.clawdbot/skills/skill-manager/
cp -r tests/ ~/.clawdbot/skills/skill-manager/
```

## Usage

### Register a Skill

```python
from skill_manager import SkillManager

manager = SkillManager()

# Register a new skill
result = manager.register_skill("./skills/my-new-skill")
print(result)
# {"success": True, "skill_name": "my-new-skill", "version": "0.1.0"}
```

### Health Check

```python
# Check single skill
health = manager.check_health("my-new-skill")
print(health)
# {"status": "healthy", "health_score": 100, ...}

# Check all skills
results = manager.health_check_all()
print(f"Healthy: {results['healthy']}/{results['total']}")
```

### Backup

```python
# Backup before update
result = manager.backup_skill("my-new-skill")
print(result["backup_path"])
# /home/user/skills/backups/my-new-skill_v0.1.0_20260131_020000
```

### CLI

```bash
# Register
python skill_manager.py register ./skills/my-skill

# Health check
python skill_manager.py health my-skill

# List all
python skill_manager.py list

# Check all health
python skill_manager.py check-all
```

## TDD Principles Applied

Following @Delamain's deterministic feedback approach:

1. **Tests First**: All functionality tested before implementation
2. **Deterministic**: Checksum-based verification ensures consistency
3. **Objective Done**: Health score provides clear pass/fail criteria

## Skill Structure

Valid skills must have:
```
skill-name/
├── SKILL.md        # Required - documentation
└── main.py         # Required - entry point
```

## Health Score

| Score | Status | Meaning |
|-------|--------|---------|
| 100 | healthy | All checks pass |
| 80 | degraded | Checksum mismatch (modified) |
| 70 | degraded | Missing code files |
| 50 | degraded | Missing SKILL.md |
| 0 | error | Path doesn't exist |

## Safety Features

- **SKILL.md Validation**: Rejects skills without documentation
- **Checksum Tracking**: Detects unauthorized modifications
- **Automatic Backups**: Prevents data loss
- **Health Monitoring**: Continuous status checking

## Integration with AIS

Part of Agent-Infrastructure-Suite:
- Uses `state_syncer` for registry persistence
- Works with `skill_auditor` for security scanning
- Respects `model_router` quota management

## Author

JARVIS-Koz | Built with TDD 🧪
