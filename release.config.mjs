// Share revert parsing between version calculation and release notes, including scopes.
const parserOpts = {
  revertPattern: /^revert(?:\([^)]+\))?!?:\s"?([\s\S]+?)"?\s*This reverts commit (\w*)\./i,
  revertCorrespondence: ["header", "hash"],
};

export default {
  branches: ["main"],
  repositoryUrl: "https://github.com/please-behave/action.git",
  tagFormat: "v${version}",
  plugins: [
    ["@semantic-release/commit-analyzer", {
      preset: "conventionalcommits",
      parserOpts,
      releaseRules: [
        { breaking: true, release: "major" },
        { type: "feat", release: "minor" },
        ...["fix", "perf", "revert", "chore", "refactor", "config"].map(type => ({ type, release: "patch" })),
        // Ignore generated version commits.
        { type: "build", scope: "!release", release: "patch" },
        { type: "build", scope: null, release: "patch" },
        { type: "build", scope: "release", release: false },
        ...["ci", "docs", "style", "test"].map(type => ({ type, release: false })),
      ],
    }],
    ["@semantic-release/release-notes-generator", {
      preset: "conventionalcommits",
      parserOpts,
      presetConfig: {
        types: [
          { type: "feat", section: "Features" },
          { type: "fix", section: "Bug Fixes" },
          { type: "perf", section: "Performance Improvements" },
          { type: "chore", section: "Maintenance" },
          { type: "build", scope: "release", hidden: true },
          { type: "build", section: "Build System" },
          { type: "refactor", section: "Code Refactoring" },
          { type: "revert", section: "Reverts" },
          { type: "config", section: "Configuration" },
          ...["ci", "docs", "style", "test"].map(type => ({ type, hidden: true })),
        ],
      },
    }],
    "./.github/scripts/semantic-release-plugin.mjs",
    ["@semantic-release/github", {
      successComment: false,
      failComment: false,
      releasedLabels: false,
    }],
  ],
};
