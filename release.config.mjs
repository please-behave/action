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
        ...["fix", "perf", "revert"].map(type => ({ type, release: "patch" })),
        ...["build", "chore", "ci", "config", "docs", "refactor", "style", "test"].map(type => ({ type, release: false })),
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
          { type: "revert", section: "Reverts" },
          ...["build", "chore", "ci", "config", "docs", "refactor", "style", "test"].map(type => ({ type, hidden: true })),
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
