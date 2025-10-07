# Release Process

This document describes how to create a new release of the VirtualBox EDR Malware Analysis System.

## Automated Release Process

The project uses GitHub Actions to automatically create releases when a new tag is pushed.

### Creating a Release

1. **Using the release script (Recommended)**:
   ```bash
   # Make sure you're on the main branch and have the latest changes
   git checkout main
   git pull origin main
   
   # Create a new release (replace 1.0.1 with your desired version)
   python scripts/release.py 1.0.1
   ```

2. **Manual process**:
   ```bash
   # Update version in files
   # Edit app/__init__.py and main.py to update version numbers
   
   # Commit changes
   git add .
   git commit -m "Bump version to 1.0.1"
   
   # Create and push tag
   git tag -a v1.0.1 -m "Release v1.0.1"
   git push origin main
   git push origin v1.0.1
   ```

### What Happens Automatically

When you push a tag starting with `v` (e.g., `v1.0.1`), GitHub Actions will:

1. **Update version numbers** in relevant files
2. **Create source archives** (tar.gz and zip)
3. **Generate changelog** from git commits
4. **Create a GitHub release** with:
   - Release notes
   - Download links
   - Installation instructions
   - System requirements

### Release Naming Convention

- Use semantic versioning: `MAJOR.MINOR.PATCH`
- Examples: `1.0.0`, `1.0.1`, `1.1.0`, `2.0.0`
- Pre-releases: `1.0.0-alpha.1`, `1.0.0-beta.1`, `1.0.0-rc.1`

### Version Bumping Guidelines

- **PATCH** (1.0.0 → 1.0.1): Bug fixes, security patches
- **MINOR** (1.0.0 → 1.1.0): New features, improvements
- **MAJOR** (1.0.0 → 2.0.0): Breaking changes, major rewrites

## Pre-Release Checklist

Before creating a release, ensure:

- [ ] All tests pass: `make test`
- [ ] Code is properly formatted: `make format`
- [ ] No linting errors: `make lint`
- [ ] Documentation is up to date
- [ ] CHANGELOG.md is updated (if manually maintained)
- [ ] Version numbers are consistent
- [ ] All features are tested with actual VMs

## Post-Release Tasks

After a release is created:

1. **Verify the release** on GitHub
2. **Test the download links** work correctly
3. **Update documentation** if needed
4. **Announce the release** to users
5. **Monitor for issues** and be ready to create patch releases

## Hotfix Releases

For urgent bug fixes:

1. Create a hotfix branch from the release tag:
   ```bash
   git checkout v1.0.0
   git checkout -b hotfix/1.0.1
   ```

2. Make the necessary fixes
3. Test thoroughly
4. Create a new release following the normal process

## Release Notes Template

Each release should include:

- **New Features**: What's new in this version
- **Bug Fixes**: What issues were resolved
- **Improvements**: Performance or usability enhancements
- **Breaking Changes**: Any incompatible changes
- **Known Issues**: Any known problems
- **Upgrade Instructions**: How to upgrade from previous versions

## Rollback Process

If a release has critical issues:

1. **Create a hotfix** with the fix
2. **Release a new patch version** immediately
3. **Update documentation** to recommend the new version
4. **Consider marking the problematic release** as a pre-release

## Support Policy

- **Latest major version**: Full support
- **Previous major version**: Security fixes only
- **Older versions**: No support (users should upgrade)

For questions about the release process, please open an issue or contact the maintainers.
