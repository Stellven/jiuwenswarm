# Construct source inside the task-owned checkout

Use inspect and read to examine source without a shell. The API requires the current task's constraints.local_commits=true and allowed_effects containing workspace.write, including for inspection. The checkout is exactly FACTORY_HOME/agent-workspace/source.subpath and must be an isolated Git clone. No caller-supplied repository path is accepted.

Inspect returns HEAD, tree, status and at most 500 file names per page. An optional prefix filters the file list. Read accepts a relative path, byte offset and page limit up to 262144 bytes. Its SHA256 covers the complete file, which must be regular, singly linked and at most 1 MiB. Read page boundaries may replace split UTF-8 characters; use ASCII byte boundaries when reconstructing a file.

Write accepts the complete UTF-8 text and expected_sha256 from read, or null for a new file. It refuses stale identity and atomically replaces the file. Parent directories may be created inside the checkout. Absolute paths, traversal, .git metadata paths, symlinks and hardlinked source files are refused. The maximum file size is 1 MiB.

Edit accepts path, expected_sha256, result_sha256 and 1..64 replacements [{old, new}]. Each nonempty old string must match exactly once in the evolving text. All edits and the expected final digest are checked before the existing atomic write. Use exact literal hunks from reviewed material when the shell is unavailable; read enough context to disambiguate each hunk. Any mismatch leaves the original file intact. No patch commands are executed.

Localcommit accepts 1..64 explicit relative file paths, a message and expected_head from inspect. It refuses existing staged changes and a stale HEAD. Git plumbing hashes raw source bytes, creates a tree and local commit, and advances HEAD with a compare-and-swap. Hooks, clean/smudge filters, signing, editors and remote operations are disabled. Other unstaged files remain uncommitted. If interrupted, inspect HEAD and status before retrying; an interrupted ref/index update may require operator recovery. No remote is contacted and nothing is pushed.

Choose each source change from retained evidence. After localcommit, use the returned commit with the existing Builder or prepare_experiment build request under the unchanged operator envelope. This workbench does not build, launch GPU jobs, change acceptance rules or promote a candidate.
