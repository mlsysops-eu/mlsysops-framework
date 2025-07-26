# Setup a Development Environment

Most of the environment setup steps are already covered in the [Installation Guide](../../installation.md). Please follow that document first.

---

## Clone the MLSysOps Framework

Once you've completed the prerequisites, clone the repository and navigate into it:

```bash
git clone https://github.com/mlsysops-eu/mlsysops-framework.git
cd mlsysops-framework
```

---

## Build the Framework

Depending on your development needs, you may want to build various components or run them locally. Follow the instructions in the respective README files of each module (e.g., mlsysops-cli, agents, etc.) for component-specific development workflows.

---

## Recommendations

- Use a Python virtual environment for CLI or backend development.
- Use pre-commit to enforce linting and formatting rules (see Contributing Guide).
- For advanced setup like deploying agents, check relevant module README files under the `agents/` or `mlsysops-cli/` directories.

---

## Need Help?

If you encounter issues during setup, feel free to [open an issue](https://github.com/mlsysops-eu/mlsysops-framework/issues) or refer to the [Developer Guide Index](../developer-guide/index.md).
