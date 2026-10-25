# Contributing

Start with a minimal example of a string that is misclassified, a proposed patch that changes behavior, or a catalog problem that is missed. Include the command, Python/Godot versions, expected result, and actual result. Use synthetic text; do not post private project source or credentials.

Run `python -m unittest discover -s tests -v` before opening a pull request. For scanner changes, add both a display-text example and a similar machine-data example. For patch changes, verify the second pass proposes no further change and exercise the result in Godot.

Prefer abstaining from a change over guessing that a string is player-facing. Avoid rewriting whole files, executing project code during scanning, or adding network calls. Keep JSON output useful to other tools and document compatibility changes.

Work toward external-project validation, but respect each upstream project's license and keep borrowed assets outside this repository. Source availability is not permission to relicense another project's work.

Contributions are accepted under the repository's MIT license. There is no contributor license agreement.
