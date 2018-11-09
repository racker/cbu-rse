# Contributing

## Development Conventions

For reference, the repo is structured along the lines described
[here][pp].

### Branches and Tags

1. There are two ongoing branches, `develop` and `master`. New code gets
   added or merged into `develop`. `master` is for releases only.
2. Tag releases after they are merged to master. RSE's version is
   autodetected from these tags at build time.
3. Each release is a minor version bump. Post-release fixes are a patch
   version bump. Don't change release tags if you can avoid it.
   Definitely don't change them after a version hits prod.[^1]
4. Don't create topic branches in the canonical repo without a good
   reason. Keep them in your own repo.

Context: At time of writing we have a crapton of defunct pointless
branches and tags in the canonical repo. This should not happen.

### Commits and PRs

1. Take the time to write good commit messages, *at least* for the
   subject line.
2. Ideally, individual commits should do exactly one significant thing.
   But you don't need to be obsessive about it.
3. If you're comfortable with rebasing, you can usually achieve #2 with
   `git rebase -i --onto develop...HEAD` or similar. If you're not
   comfortable rebasing, don't worry about it.
4. When submitting PRs, remember that Github uses the PR's subject and
   body as defaults for the resulting merge commit. Put some thought
   into them.
5. After your PR is merged, if it was squashed/rebased, you should
   probably check out a new topic branch. If you'd rather keep it, you
   can fix it to account for the squash with `git fetch upstream; git
   rebase --fork-point upstream/develop`.

Context: These are intended to keep history readable.

### Merging PRs

1. If the PR is a single commit, or a single logical change with
   irrelevant fixups, prefer squash merge. This avoids useless merge
   bubbles.
2. If the PR contains several related non-trivial commits, prefer
   a normal merge. This preserves information about which commits are
   related to each other.
3. If the PR history is perfectly clean and contains multiple logical
   changes, *then* you can consider a rebase merge. But be really
   careful.
4. For normal merges, *include a useful commit message in the merge,
   especially the subject line.* The default "Merge PR #XX from
   user/branch" is not useful. The merge subject should summarize what,
   exactly, is being merged.

Context: #1 and #2 make `git log --oneline --graph` easy to understand.
Consistently applying #3 and #4 allows `git log --oneline
--first-parent` to spit out a concise list of feature additions and bug
fixes, suitable for generating a changelog.

In fact that makes for a good rule of thumb: Aim for a history such that
each commit on develop's first-parent is testable, and has a 1:1
correspondence with a changelog entry. It will never be perfect, but
should be close.

FIXME: Something to maybe add later: have tests fail if the commit log
doesn't match standards with commitlint or similar, eg. [logtests][]

[^1]: Changing a tag breaks the ability to track which commit a build
      was built from -- e.g. if you change where v1.13.23 points, and we
      see v1.13.23 in production, we don't know whether it was built
      from the old commit or the new one.

[logtests]: https://blog.mozilla.org/webdev/2016/07/15/auto-generating-a-changelog-from-git-history/
[pp]: https://blog.ionelmc.ro/2014/05/25/python-packaging/
