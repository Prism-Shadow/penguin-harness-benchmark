# frozen_string_literal: true

# Per-node behavior asset.  The shared runtime loader still evaluates the real
# production files from REPO_DIR; this wrapper contributes no production API.
task_root = ENV["TASK_ROOT"] || File.expand_path("../..", __dir__)
load File.join(task_root, "environment", "behavior_runner.rb")
BehaviorRunner.run(827)
