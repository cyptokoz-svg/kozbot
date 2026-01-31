#!/usr/bin/env python3
"""
test_skill_manager.py - TDD Tests for Skill Manager

Test-first development following @Delamain's deterministic feedback principle.
"""

import unittest
import json
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from skill_manager import SkillManager, SkillStatus, SkillState


class TestSkillStatus(unittest.TestCase):
    """Test SkillStatus dataclass behavior."""
    
    def test_skill_status_creation(self):
        """RED: Should create a SkillStatus with all fields."""
        # This test will fail until SkillStatus is implemented
        from skill_manager import SkillStatus
        
        status = SkillStatus(
            name="test-skill",
            version="1.0.0",
            path="/tmp/test",
            status="active",
            last_check="2026-01-31T02:00:00Z"
        )
        
        self.assertEqual(status.name, "test-skill")
        self.assertEqual(status.version, "1.0.0")
        self.assertEqual(status.status, "active")


class TestSkillManagerInit(unittest.TestCase):
    """Test SkillManager initialization."""
    
    def test_manager_creates_config_dir(self):
        """RED: Should create config directory on init."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SkillManager(base_path=tmpdir)
            config_file = Path(tmpdir) / "skill_registry.json"
            self.assertTrue(config_file.exists())
    
    def test_manager_loads_existing_registry(self):
        """RED: Should load existing registry if present."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-create registry
            registry_file = Path(tmpdir) / "skill_registry.json"
            with open(registry_file, 'w') as f:
                json.dump({"skills": []}, f)
            
            manager = SkillManager(base_path=tmpdir)
            self.assertEqual(len(manager.skills), 0)


class TestSkillRegistration(unittest.TestCase):
    """Test skill registration functionality."""
    
    def test_register_new_skill(self):
        """RED: Should register a new skill from path."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock skill
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Test Skill")
            (skill_dir / "main.py").write_text("# Main code")
            
            manager = SkillManager(base_path=tmpdir)
            result = manager.register_skill(skill_dir)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["skill_name"], "test-skill")
            self.assertEqual(len(manager.skills), 1)
    
    def test_register_invalid_skill(self):
        """RED: Should reject skill without SKILL.md."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "invalid-skill"
            skill_dir.mkdir()
            # No SKILL.md
            
            manager = SkillManager(base_path=tmpdir)
            result = manager.register_skill(skill_dir)
            
            self.assertFalse(result["success"])
            self.assertIn("SKILL.md", result["error"])


class TestSkillHealthCheck(unittest.TestCase):
    """Test skill health checking."""
    
    def test_health_check_passes_for_valid_skill(self):
        """RED: Should pass health check for valid skill."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "healthy-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Healthy")
            (skill_dir / "main.py").write_text("print('OK')")
            
            manager = SkillManager(base_path=tmpdir)
            manager.register_skill(skill_dir)
            
            health = manager.check_health("healthy-skill")
            self.assertEqual(health["status"], "healthy")
            self.assertTrue(health["has_skill_md"])
            self.assertTrue(health["has_code_files"])
    
    def test_health_check_fails_for_missing_files(self):
        """RED: Should fail if main code file missing."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "broken-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Broken")
            # No main.py
            
            manager = SkillManager(base_path=tmpdir)
            manager.register_skill(skill_dir)
            
            health = manager.check_health("broken-skill")
            self.assertEqual(health["status"], "degraded")
            self.assertFalse(health["has_code_files"])


class TestSkillBackup(unittest.TestCase):
    """Test skill backup functionality."""
    
    def test_backup_creates_archive(self):
        """RED: Should create backup archive of skill."""
        from skill_manager import SkillManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "backup-test"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Backup")
            (skill_dir / "main.py").write_text("# Code")
            
            manager = SkillManager(base_path=tmpdir)
            manager.register_skill(skill_dir)
            
            backup_dir = Path(tmpdir) / "backups"
            result = manager.backup_skill("backup-test", backup_dir)
            
            self.assertTrue(result["success"])
            self.assertTrue(Path(result["backup_path"]).exists())


if __name__ == "__main__":
    # Run with: python -m pytest test_skill_manager.py -v
    # Or: python test_skill_manager.py
    unittest.main(verbosity=2)
