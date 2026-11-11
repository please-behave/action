#!/usr/bin/env bash
set -euo pipefail
trap 'echo "::error::Please Behave installation failed at line $LINENO. Check the release tag, release assets and network access." >&2' ERR

if [[ "$PLEASE_RUN" != true && "$PLEASE_RUN" != false ]]; then
  echo "::error::run must be true or false." >&2
  exit 1
fi
if [[ "$PLEASE_SUMMARY" != true && "$PLEASE_SUMMARY" != false ]]; then
  echo "::error::summary must be true or false." >&2
  exit 1
fi
if [[ "${PLEASE_CHECKS_ONLY-false}" != true && "${PLEASE_CHECKS_ONLY-false}" != false ]]; then
  echo "::error::checks-only must be true or false." >&2
  exit 1
fi
if [[ "${PLEASE_INSTALL-true}" != true && "${PLEASE_INSTALL-true}" != false ]]; then
  echo "::error::install must be true or false." >&2
  exit 1
fi
if [[ "${PLEASE_SYNC-false}" != true && "${PLEASE_SYNC-false}" != false ]]; then
  echo "::error::sync must be true or false." >&2
  exit 1
fi
if [[ "${PLEASE_INSTALL-true}" == false ]]; then
  if ! command -v please >/dev/null; then
    echo "::error::install is false but please is missing from PATH. Install the published CLI first." >&2
    exit 1
  fi
  exit 0
fi
if [[ ! "${PLEASE_VERSION-}" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "::error::version must be an exact stable release tag, such as v1.2.3." >&2
  exit 1
fi
case "$RUNNER_OS/$RUNNER_ARCH" in
  Linux/X64) target=x86_64-unknown-linux-gnu ;;
  Linux/ARM64) target=aarch64-unknown-linux-gnu ;;
  macOS/X64) target=x86_64-apple-darwin ;;
  macOS/ARM64) target=aarch64-apple-darwin ;;
  *) echo "::error::Unsupported runner platform: $RUNNER_OS/$RUNNER_ARCH" >&2; exit 1 ;;
esac

work=$(mktemp -d "$RUNNER_TEMP/please-download.XXXXXX")
trap 'rm -rf "$work"' EXIT
name="please-$PLEASE_VERSION-$target"
archive="$name.tar.gz"
base="https://github.com/please-behave/cli/releases/download/$PLEASE_VERSION"
curl --fail --show-error --silent --location --retry 3 --connect-timeout 15 --max-time 120 "$base/$archive" -o "$work/$archive"
curl --fail --show-error --silent --location --retry 3 --connect-timeout 15 --max-time 120 "$base/SHA256SUMS" -o "$work/SHA256SUMS"
# Select exactly this archive; other platform downloads are not needed.
awk -v archive="$archive" '$2 == archive && $1 ~ /^[0-9a-f]+$/ && length($1) == 64 { print; count++ } END { if (count != 1) exit 1 }' "$work/SHA256SUMS" > "$work/selected-sum"
if [[ "$RUNNER_OS" == macOS ]]; then
  (cd "$work" && shasum -a 256 --check selected-sum)
else
  (cd "$work" && sha256sum --check selected-sum)
fi
tar -xzf "$work/$archive" -C "$work" -- "$name/please"
if [[ ! -f "$work/$name/please" || -L "$work/$name/please" ]]; then
  echo "::error::Release archive has no regular please executable." >&2
  exit 1
fi
bin="$RUNNER_TEMP/please/bin"
mkdir -p "$bin"
install -m 755 "$work/$name/please" "$bin/please"
printf '%s\n' "$bin" >> "$GITHUB_PATH"
echo "Installed Please Behave $PLEASE_VERSION ($target)."
