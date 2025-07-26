---
layout: default
title: "Contributing"
description: "Contributing guidelines"
---

# 🛠️ How to Contribute

Welcome! 👋 We're thrilled you're considering contributing to the **MLSysOps Framework**. This guide will help you get started.

---

## 📌 Table of Contents

- [Ground Rules](#-ground-rules)
- [Code of Conduct](#-code-of-conduct)
- [Ways to Contribute](#-ways-to-contribute)
- [How to Submit a PR](#-how-to-submit-a-pr)
- [Writing Good Commit Messages](#-writing-good-commit-messages)
- [Issue Labels](#-issue-labels)
- [Branching Strategy](#-branching-strategy)
- [Contact](#-contact)

---

## 📋 Ground Rules

- Be respectful and considerate to others.
- Make sure your contributions align with the project's goals.
- Write clear, concise, and grammatically correct Markdown.
- Ensure documentation and code are easy to read and understand.
- When in doubt, open an issue and ask for guidance.

---

## 🤝 Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](../../CODE_OF_CONDUCT.md). Please take a moment to read it.

---

## ✨ Ways to Contribute

We welcome contributions of all kinds, including:

- 📖 Improving documentation and fixing typos
- 💡 Suggesting new features or enhancements
- 🐛 Reporting bugs
- 🧪 Writing or improving tests
- 💻 Fixing issues
- 🌐 Translating the project
- 🧱 Improving code structure or consistency

---

## 🔀 How to Submit a PR

1. **Fork the repository**  
   Click the **Fork** button on the top-right of this repo's GitHub page.

2. **Clone your forked repo**

   ```bash
   git clone https://github.com/YOUR_USERNAME/mlsysops-framework.git
   cd mlsysops-framework
   ```

3. **Create a new branch**

   ```bash
   git checkout -b your-feature-name
   ```

4. **Make your changes**
   Ensure your code follows existing style guidelines and passes all checks.

5. **Commit your changes**

   ```bash
   git commit -m "feat: Add a descriptive message"
   ```

6. **Push your branch**

   ```bash
   git push origin your-feature-name
   ```

7. **Open a Pull Request**
   Go to the GitHub page of your fork, and click "Compare & pull request".
   Provide a clear title and description of your changes.

---

## ✍️ Writing Good Commit Messages

Follow the conventional commit format:

```bash
<type>(scope): short description
```

**Examples:**

- `feat(docs): add contributing guidelines`
- `fix(auth): resolve login redirect issue`
- `chore: update dependencies`

**Types:**

- `feat` – A new feature
- `fix` – A bug fix
- `docs` – Documentation only changes
- `style` – Changes that do not affect the meaning of the code
- `refactor` – Code changes that neither fix a bug nor add a feature
- `test` – Adding missing tests
- `chore` – Changes to the build process or tools

---

## 🏷️ Issue Labels

Our GitHub issues use the following labels to help contributors find where they can help:

- `good first issue` – Great for newcomers!
- `help wanted` – We need help with this.
- `bug` – Confirmed bugs.
- `enhancement` – Feature or improvement requests.
- `question` – Discussions or clarifications.

---

## 🌱 Branching Strategy

We follow a simple Git branching model:

- `main` – Stable, production-ready code.
- `dev` – Development branch. All features and bug fixes should branch from and merge back into dev.

**Example workflow:**

```bash
# Start from dev
git checkout dev
git pull

# Create your feature branch
git checkout -b feat/component-xyz
```

---

## 📬 Contact

If you have questions, suggestions, or just want to say hi, feel free to:

- Open an issue
- Start a discussion
- Reach out via email

Thank you for contributing to MLSysOps Framework! 💙
