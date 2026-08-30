# Contributing to DungeonMAInd

This document describes the workflow we use when working on DungeonMAInd.

The goal is to keep development organized, make changes easy to review, and keep the `main` branch in a working state.

## 1. Before Starting Work

All development work should be connected to a GitHub Issue.

Before starting:

1. Check the project board and the assigned Issue.
2. Make sure the Issue is sufficiently defined.
3. Assign yourself to the Issue if it has been assigned to you during sprint planning.
4. Move the Issue to **In Progress** when you actually begin working on it.

Do not start unrelated work without first creating or discussing an Issue.

## 2. Branches

Do not work directly on `main`.

Create a separate branch for each Issue or task.

Start from the latest version of `main`:

```bash
git switch main
git pull
git switch -c <branch-name>
```

Use descriptive branch names.

Examples:

```text
feature/timeline-editing
feature/event-detection
fix/item-false-positives
test/timeline-regression
docs/update-readme
refactor/timeline-generator
```

Branches should describe the work being done, not the person doing it.

Avoid names such as:

```text
my-branch
test
dev
murtada
student1
```

## 3. Commits

Commit regularly while working.

Commit messages should briefly describe what changed.

Good examples:

```text
Add candidate event detection
Fix item acquisition classification
Add timeline regression tests
Update GPU Docker instructions
```

Avoid unclear messages such as:

```text
fix
update
test
final
changes
```

The project requirements use Git commits as part of the documentation of individual contributions and suggest approximately five commits per person per week/sprint as a reasonable baseline.

Commits should still represent meaningful pieces of work rather than being artificially split only to increase the commit count.

## 4. Keeping Your Branch Updated

If `main` changes while you are working, update your branch before requesting final review.

For example:

```bash
git switch main
git pull

git switch <your-branch>
git merge main
```

Resolve any conflicts and test the application again before pushing.

## 5. Testing

Before opening a Pull Request:

* Make sure the application still starts.
* Test the functionality you changed.
* Check that existing related functionality still works.
* Test Docker startup if your changes affect Docker, dependencies, backend startup, Ollama, GPU support, or configuration.
* Add or update automated tests where appropriate.
* Do not commit `.env` files, passwords, API keys, tokens, or other secrets.

For AI-related changes, include realistic transcript examples where possible.

When fixing a bug, add a regression test when practical so the same bug does not return later.

## 6. Opening a Pull Request

Push your branch:

```bash
git push -u origin <branch-name>
```

Then open a Pull Request into:

```text
main
```

Use the repository Pull Request template.

Every Pull Request implementing an Issue should link it using:

```text
Closes #<issue-number>
```

Example:

```text
Closes #11
```

The Pull Request should explain:

* what was changed,
* which Issue it addresses,
* how it was tested,
* known limitations or follow-up work,
* screenshots, logs, or transcript examples where relevant.

When a Pull Request is ready for review, the related Issue should be moved to **In Review**.

## 7. Code Review

At least one other team member must review and approve the Pull Request before it can be merged.

Reviewers should check:

* whether the change solves the Issue,
* whether the implementation is understandable,
* whether obvious edge cases have been considered,
* whether existing functionality may have been broken,
* whether tests are sufficient,
* whether documentation needs updating.

If changes are requested, the author should address them and push the updates to the same branch.

All review conversations should be resolved before merging.

The author cannot approve their own Pull Request.

## 8. Merging

Pull Requests are merged using **Squash and merge**.

Do not use direct pushes to `main`.

After the Pull Request is merged:

1. The related Issue should close automatically when it was linked using `Closes #...`.
2. The Issue status becomes **Done**.
3. The feature branch is automatically deleted.
4. Pull the updated `main` before beginning new work.

```bash
git switch main
git pull
```

## 9. Project Board Workflow

Issues move through the project board using the following states:

```text
Backlog
   ↓
Ready
   ↓
In Progress
   ↓
In Review
   ↓
Done
```

Use **Blocked** when work cannot currently continue.

### Backlog

Known work that has not been selected for the current sprint.

### Ready

The task has been discussed, is sufficiently defined, and can be started.

### In Progress

Someone is actively working on the task.

### In Review

Implementation is complete and a Pull Request is being reviewed or tested.

### Blocked

The task cannot continue because another problem, decision, dependency, or task must be resolved first.

### Done

The work is completed and merged into `main`.

## 10. Sprint Workflow

DungeonMAInd uses weekly sprints.

During sprint planning:

1. Review the Backlog.
2. Decide which Issues should be completed during the sprint.
3. Assign responsible team members.
4. Assign the Issues to the current GitHub Iteration.
5. Move selected work from **Backlog** to **Ready**.

During the sprint:

* Move an Issue to **In Progress** when work begins.
* Use **Blocked** when something prevents progress.
* Move work to **In Review** when the Pull Request is ready.
* Completed and merged work becomes **Done**.

At the weekly sprint meeting, discuss:

* what was completed,
* what is currently being worked on,
* problems or blockers,
* tasks taking longer than expected,
* what should be worked on next,
* who will take responsibility for upcoming work.

A short sprint meeting document should be created after each meeting.

## 11. Issues

Use the provided Issue templates when possible.

### Bug Report

Use for incorrect or unexpected existing behavior.

Examples:

* false-positive timeline events,
* Docker startup failure,
* incorrect entity extraction,
* frontend errors.

### Feature / Improvement Request

Use for new functionality or improvements to existing functionality.

Use appropriate labels such as:

```text
bug
feature
enhancement
backend
frontend
AI/ML
docker
testing
documentation
high-priority
blocked
```

Use the appropriate Release milestone for work belonging to a specific release.

## 12. Definition of Done

An Issue should only be considered complete when:

* the requested functionality is implemented,
* relevant testing has been performed,
* obvious regressions have been checked,
* tests are added or updated where appropriate,
* documentation is updated where necessary,
* the Pull Request has been reviewed and approved,
* review comments have been resolved,
* the change has been merged into `main`.

A feature merely existing on someone's branch does **not** mean it is finished.
