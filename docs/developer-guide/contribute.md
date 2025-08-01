---
layout: default
title: "Contributing"
description: "Contributing guidelines"
---

The MLSysOps framework is an open-source project licensed under the [Apache
License
2.0](https://github.com/mlsysops-eu/mlsysops-framework/blob/main/LICENSE).
We welcome anyone who would be interested in contributing to `MLSysOps framework`.
As a first step, please take a look at the following document.
The current document provides a high level overview of `MLSysOps framework`'s code structure, along with a few guidelines regarding contributions to the project.

## Table of contents:

1. [Code organization](#code-organization)
2. [How to contribute](#how-to-contribute)
3. [Opening an issue](#opening-an-issue)
4. [Requesting new features](#requesting-new-features)
5. [Submitting a PR](#submitting-a-pr)
6. [Style guide](#style-guide)
7. [Contact](#contact)

## Code organization

The MLSysOps framework is structured as follows:

TBC

## How to contribute

There are plenty of ways to contribute to an open source project, even without changing or touching the code.
Therefore, anyone who is interested in this project is very welcome to contribute in one of the following ways:

1.  Using `MLSysOps framework`. Try it out yourself and let us know your experience. Did everything work well? Were the instructions clear?
2.  Improve or suggest changes to the documentation of the project. Documentation is a very important part of every project, hence any ideas on how to make it more clear are more than welcome.
3.  Request new features. Any proposals for improving existing features or adding new ones are very welcome.
4.  Find a bug and report it. Bugs are everywhere and some are hidden very well. As a result, if you find a bug, we would really appreciate it if you reported it to the maintainers.
5.  Make changes to the code. Improve the code, add new functionality, and make `MLSysOps framework` even more useful.

## Opening an issue

We use Github issues to track bugs and requests for new features.
Anyone is welcome to open a new issue, either to report a bug or to request a new feature.

### Reporting bugs

To report a bug or misbehavior in `MLSysOps framework`, a user can open a new issue explaining the problem.
For the time being, we do not have a strict template for reporting issues, however, it is important that enough information is provided for the problem to be easily identified and resolved.
To that end, when opening a new issue regarding a bug, we kindly ask you to:

- Mark the issue with the bug label
- Provide the following information:
  1. A short description of the bug.
  2. The respective logs both from the output and `containerd`.
  3. Framework's version manifest (either the commit hash or the version manifest file).
  4. The execution environment (CPU architecture, VMM etc.).
  5. Any particular steps to reproduce the issue.

- Keep an eye on the issue for possible questions from the maintainers.

The following template may serve as a useful guide:

```
## Description
An explanation of the issue

## System info

- Version:
- Arch:
- VMM:
- ...

## Steps to reproduce
A list of steps that can reproduce the issue.
```

### Requesting new features

We are very happy to hear about features that you would like to see in `MLSysOps framework`.
One way to communicate such a request is using Github issues.
For the time being, we do not use a strict template for requesting new features, however, we kindly ask you to mark the issue with the enhancement label and provide a description of the feature.

## Submitting a PR

Everyone should feel free to submit a change or an addition to the codebase of `MLSysOps framework`.
Currently, we use Github's Pull Requests (PRs) to submit changes to `MLSysOps framework`'s codebase.
Before creating a new PR, please follow the guidelines below:

- Make sure that the changes do not break the building process of `MLSysOps framework`.
- Make sure that all tests run successfully.
- Make sure to sign-off your commits.
- Provide meaningful commit messages, briefly describing the changes.
- Provide a meaningful PR message.

As soon as a new PR is created the following workflow will take place:

1. The creator of the PR should invoke the tests by adding the `ok-to-test` label.
2. If the tests pass, request that one or more `MLSysOps framework`'s [maintainers](https://github.com/nubificus/MLSysOps framework/blob/main/MAINTAINERS) review the PR.
3. The reviewers submit their review.
4. The author of the PR should address all the comments from the reviewers.
5. As soon as a reviewer approves the PR, an action will add the appropriate git trailers in the PR's commits.
6. The reviewer who accepted the changes will merge them.

## Labels for the CI

We use github workflows to invoke some tests when a new PR opens for `MLSysOps framework`.
In particular, we perform the following workflows tests:

- Commit message linting: Please check the [git commit message style](#git-commit-messages) below for more info.
- Spell checking: since the `MLSysOps framework` repository contains its documentation too.
- License check
- Code linting
- Building artifacts for amd64 and aarch64.
- Unit tests
- End-to-end tests

For better control over the tests and workflows that run in a PR, we define three PR labels:

- `ok-to-test`: Runs a full CI workflow, meaning all lint tests (commit
  message, spellcheck, license), Code linting, building for x86 and aarch64,
  unit tests, and finally, end-to-end tests.
- `skip-build`: Skips the building workflows along with unit test and end-to end tests, while still running all linters. This is useful when
  the PR is related to docs because it can help catch spelling errors, etc. In
  addition, if the changes are not related to the codebase, running the
  end-to-end tests is not required and saves some time.
- `skip-lint`: Skips the linting phase. This is particularly useful on draft
  PRs, when we want to just test the functionality of the code (either a bug
  fix, or a new feature) and defer the cleanup/polishing of commits, code, and
  docs until the PR will be ready for review.

**Note**: Both `skip-build` and `skip-lint` assume that the `ok-to-test` label
is added.

## Style guide

### Git commit messages

Please follow the guidelines below for your commit messages:

- Limit the first line to 72 characters or less.
- Limit all other lines to 80 characters.
- Follow the [Conventional Commits](https://www.conventionalcommits.org/)
  specification and, specifically, format the header as `<type>[optional scope]:
<description>`, where `description` must not end with a full stop and `type`
  can be one of:
  - _feat_: A new feature
  - _fix_: A bug fix
  - _docs_: Documentation only changes
  - _style_: Changes that do not affect the meaning of the code (white-space,
    formatting, missing semi-colons, etc)
  - _refactor_: A code change that neither fixes a bug nor adds a feature
  - _`perf`_: A code change that improves performance
  - _test_: Adding missing tests
  - _build_: Changes that affect the build system or external dependencies
    (example scopes: `gulp`, `broccoli`, `npm`)
  - _ci_: Changes to our CI configuration files and scripts (example scopes:
    `Travis`, `Circle`, `BrowserStack`, `SauceLabs`)
  - _chore_: Other changes that don't modify source code or test files
  - _revert_: Reverts a previous commit

- In case the PR is associated with an issue, please refer to it, using the git trailer `Fixes: #<issue number>`, i.e. `Fixes: #30`.
- Always sign-off your commit message.

Since the `MLSysOps framework` comprises code written in various programming
languages, we use the following styles for each:

### Golang code style

We follow `gofmt`'s formatting rules. Therefore, we ask all
contributors to do the same. Go provides the `gofmt` tool, which can be used
for formatting your code.

### Python

TBC

### C

TBC

## Contact

Feel free to contact any of the
[maintainers](https://github.com/mlsysops-eu/mlsysops-framework/blob/main/MAINTAINERS)
or using one of the below email addresses:

- info@mlsysops.eu
