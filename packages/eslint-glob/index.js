const { isAbsolute } = require("node:path");
const { globSync: tinyGlobSync } = require("tinyglobby");

/**
 * Implement the directory-globbing API used by Next's getRootDirs helper.
 * tinyglobby avoids the unpatched braces dependency, but its defaults expand
 * literal directories recursively and return relative paths for absolute input.
 * Preserve fast-glob's behavior so explicit monorepo roots keep working.
 *
 * @param {string} pattern A Next.js root directory path or glob.
 * @param {{ onlyDirectories?: boolean }} options Options supplied by Next.js.
 * @returns {string[]} Matching root paths, without extra descendant directories.
 */
function globSync(pattern, options = {}) {
  const matches = tinyGlobSync(pattern, {
    ...options,
    absolute: isAbsolute(pattern),
    expandDirectories: false,
  });

  // fast-glob retains a trailing slash only when the input includes one.
  return pattern.endsWith("/")
    ? matches
    : matches.map((match) => match.replace(/\/$/, ""));
}

module.exports = { globSync };
