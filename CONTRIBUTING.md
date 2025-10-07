# Contributing to VirtualBox EDR Malware Analysis System

Thank you for your interest in contributing to this project! We welcome contributions from the community.

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- VirtualBox 7.0+
- Git
- Basic understanding of malware analysis and virtualization

### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/your-username/vmm.git
   cd vmm
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```

4. **Set up pre-commit hooks** (optional but recommended)
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## 📝 How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/zcyberseclab/vmm/issues)
2. If not, create a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (OS, Python version, VirtualBox version)
   - Log files if applicable

### Suggesting Features

1. Check [Issues](https://github.com/zcyberseclab/vmm/issues) for existing feature requests
2. Create a new issue with:
   - Clear description of the feature
   - Use case and benefits
   - Possible implementation approach

### Code Contributions

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation if needed

3. **Test your changes**
   ```bash
   python -m pytest tests/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: your feature description"
   ```

5. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📋 Code Style Guidelines

### Python Code Style

- Follow PEP 8
- Use type hints where possible
- Write docstrings for functions and classes
- Keep functions small and focused
- Use meaningful variable names

### Commit Message Format

```
Type: Brief description

Detailed description if needed

- Add: New feature
- Fix: Bug fix
- Update: Modify existing feature
- Remove: Delete code/feature
- Docs: Documentation changes
- Test: Add or modify tests
- Refactor: Code refactoring
```

### Testing

- Write unit tests for new functions
- Ensure all tests pass before submitting PR
- Test with different VM configurations if possible

## 🔍 Areas for Contribution

### High Priority
- Additional EDR integrations
- Performance optimizations
- Better error handling
- Documentation improvements

### Medium Priority
- Linux malware analysis support
- Web UI improvements
- Additional file format support
- Enhanced reporting features

### Low Priority
- Code refactoring
- Additional test coverage
- Performance benchmarks

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [VirtualBox SDK](https://www.virtualbox.org/sdkref/)
- [Sysmon Documentation](https://docs.microsoft.com/en-us/sysinternals/downloads/sysmon)

## 🤝 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the project's coding standards

## ❓ Questions?

If you have questions about contributing, feel free to:
- Open an issue with the "question" label
- Start a discussion in [GitHub Discussions](https://github.com/zcyberseclab/vmm/discussions)
- Contact the maintainers

Thank you for contributing! 🎉
