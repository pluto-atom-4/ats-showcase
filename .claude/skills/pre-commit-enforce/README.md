# Pre-Commit Enforcement Skill

Block commits to protected branches. Enforce feature branch workflow.

## Quick Start (30 seconds)

```bash
# 1. Copy skill to project
cp -r .claude/skills/pre-commit-enforce .claude/skills/

# 2. Run setup
bash .claude/skills/pre-commit-enforce/setup.sh

# 3. Test
git commit --allow-empty -m "test"  # ❌ Blocked
git checkout -b feat/test
git commit --allow-empty -m "test"  # ✅ Works
```

## Default Behavior

- **Protects**: `main` branch
- **Allows**: All other branches (`feat/*`, `fix/*`, `docs/*`, etc.)
- **Message**: "Direct commits to main are not allowed."

## Customize

Edit `.claude/settings.json`:

```json
{
  "skillConfigs": {
    "pre-commit-enforce": {
      "protectedBranches": ["main", "staging"],
      "message": "Feature branch required"
    }
  }
}
```

Then reinstall:
```bash
bash .claude/skills/pre-commit-enforce/setup.sh
```

## Docs

See [SKILL.md](SKILL.md) for full documentation.

## Workflow

```
git checkout -b feat/issue-123-description    # Create feature branch
git commit -m "description"                     # Commit on branch
git push -u origin feat/issue-123-description   # Push branch
# Create PR on GitHub → Merge
```

## Support

- Check `.git/hooks/pre-commit` is executable: `ls -la .git/hooks/`
- Verify config: `cat .claude/settings.json | python3 -m json.tool`
- Reinstall: `bash .claude/skills/pre-commit-enforce/setup.sh`

---

**Install time**: < 1 minute
**No dependencies**: Uses bash + git
**Cross-platform**: Works on Linux, macOS, WSL
