# Contributing to prism

Thanks for looking. A few things that make a change easy to accept.

## Reporting a problem

Open an issue and include:

- what you ran (the exact command)
- what happened, and what you expected
- your Python version (`python --version`)

If it is a bug in a code path, a failing test is worth more than a paragraph.

## Sending a change

1. Fork, branch from `main`.
2. Keep the change focused. One concern per pull request — a PR that renames
   files and fixes a bug gets rubber-stamped, not read.
3. Add or update a test. Every behaviour in this repo is covered by one, and an
   untested change will be asked for one before merge.
4. Run the suite and make sure it passes:

   ```bash
   python -m pytest -q
   ```

## Code style

- Standard library only. A pull request that adds a dependency needs to argue
  why the premise of the project still holds — most of these exist specifically
  because they have none.
- No framework idioms borrowed from elsewhere. If the file needs a comment to
  explain what a line does, rename something instead.
- Type hints on public functions. They are the contract.

## What gets asked in review

- Does the test fail without the fix?
- Is there a number in the diff? Where does it come from?
- Does the README still describe what the code does?
