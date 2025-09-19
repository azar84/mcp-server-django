# Contributing to MCP Server Django

Thank you for your interest in contributing to the MCP Server Django project! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL (for local development)
- Git
- GitHub account

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/mcp-server-django.git
   cd mcp-server-django
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment**
   ```bash
   cp env.example .env
   # Edit .env with your settings
   ```

5. **Run Migrations**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Start Development Server**
   ```bash
   python manage.py runserver
   ```

## 🛠️ Development Guidelines

### Code Style
- Follow PEP 8 Python style guide
- Use Black for code formatting: `black .`
- Use meaningful variable and function names
- Add docstrings to classes and functions
- Keep line length under 88 characters (Black default)

### Testing
- Write tests for new features and bug fixes
- Maintain or improve test coverage
- Run tests before submitting: `python manage.py test`
- Test both success and error cases

### Commit Messages
Use conventional commit format:
```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(bookings): add Calendly provider integration
fix(auth): resolve token expiration handling
docs(readme): update deployment instructions
```

## 🏗️ Architecture

### Project Structure
```
mcp_server/
├── mcp/                    # Main Django app
│   ├── domains/           # Business domain tools
│   │   ├── bookings/     # Booking providers
│   │   ├── crm/          # CRM providers
│   │   ├── payments/     # Payment providers
│   │   └── email/        # Email providers
│   ├── models.py         # Database models
│   ├── views.py          # HTTP views
│   ├── protocol.py       # MCP protocol handler
│   └── mcp_transport.py  # MCP HTTP transport
├── mcp_server/            # Django project settings
└── requirements.txt       # Dependencies
```

### Adding New Providers

1. **Create Provider Class**
   ```python
   # mcp/domains/your_domain/your_provider.py
   from ..base import BaseProvider, BaseTool, ProviderType

   class YourProvider(BaseProvider):
       def __init__(self):
           super().__init__(
               name="your_provider",
               provider_type=ProviderType.YOUR_DOMAIN,
               config={}
           )
   ```

2. **Create Tool Classes**
   ```python
   class YourTool(BaseTool):
       async def _execute_with_credentials(self, arguments, credentials, context):
           # Implementation here
           return result
   ```

3. **Register in Domain Registry**
   ```python
   # mcp/domain_registry.py
   your_domain.register_provider(YourProvider())
   ```

### Database Changes
- Create migrations: `python manage.py makemigrations`
- Apply migrations: `python manage.py migrate`
- Test migrations on fresh database
- Include migration files in commits

## 🔒 Security Guidelines

### Credential Handling
- Always encrypt sensitive credentials using Fernet
- Never log or expose credentials in plain text
- Use environment variables for configuration
- Validate all input parameters

### Authentication
- Implement proper token validation
- Use scope-based access control
- Follow Django security best practices
- Test authentication edge cases

## 📝 Documentation

### Code Documentation
- Add docstrings to all public methods
- Document complex business logic
- Include examples in docstrings
- Keep documentation up to date

### API Documentation
- Document all new endpoints
- Include request/response examples
- Update OpenAPI specifications
- Test documentation examples

## 🧪 Testing Strategy

### Test Types
- **Unit Tests**: Test individual functions/methods
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Security Tests**: Test authentication and authorization

### Test Structure
```python
from django.test import TestCase
from mcp.models import Tenant, AuthToken

class TenantTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            description="Test tenant for unit tests"
        )
    
    def test_tenant_creation(self):
        self.assertEqual(self.tenant.name, "Test Tenant")
        self.assertTrue(self.tenant.is_active)
```

## 🚀 Deployment

### Heroku Deployment
- Test deployment on staging environment
- Verify environment variables
- Test migrations on production-like data
- Monitor application performance

### Environment Configuration
- Use different settings for dev/staging/production
- Secure all sensitive configuration
- Document required environment variables
- Test configuration changes

## 📋 Pull Request Process

1. **Before Submitting**
   - Fork the repository
   - Create a feature branch: `git checkout -b feature/your-feature`
   - Make your changes
   - Add tests for new functionality
   - Update documentation
   - Run tests and ensure they pass
   - Check code formatting

2. **Pull Request Template**
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] Tests pass locally
   - [ ] New tests added
   - [ ] Manual testing completed

   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] No breaking changes (or documented)
   ```

3. **Review Process**
   - Automated tests must pass
   - Code review by maintainers
   - Address feedback promptly
   - Squash commits if requested

## 🐛 Bug Reports

### Before Reporting
- Search existing issues
- Try to reproduce the bug
- Test on latest version
- Gather system information

### Bug Report Template
```markdown
**Describe the Bug**
Clear description of the bug

**To Reproduce**
1. Step 1
2. Step 2
3. Expected vs actual behavior

**Environment**
- OS: [e.g. macOS, Windows, Linux]
- Python version: [e.g. 3.9.7]
- Django version: [e.g. 4.2.7]
- Database: [e.g. PostgreSQL 13]

**Additional Context**
Logs, screenshots, etc.
```

## 💡 Feature Requests

### Before Requesting
- Check if feature already exists
- Search existing feature requests
- Consider if it fits project scope
- Think about implementation approach

### Feature Request Template
```markdown
**Feature Description**
Clear description of the proposed feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should this feature work?

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Mockups, examples, etc.
```

## 🏆 Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes for significant contributions
- GitHub contributors graph
- Special thanks for major features

## 📞 Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Documentation**: Check README and docs first
- **Code Review**: Learn from feedback on PRs

## 📜 Code of Conduct

### Our Standards
- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences
- Take responsibility for mistakes

### Unacceptable Behavior
- Harassment or discrimination
- Trolling or insulting comments
- Personal attacks
- Publishing private information
- Unprofessional conduct

### Enforcement
Violations may result in:
- Warning
- Temporary ban
- Permanent ban

Report issues to project maintainers.

---

Thank you for contributing to MCP Server Django! 🚀
