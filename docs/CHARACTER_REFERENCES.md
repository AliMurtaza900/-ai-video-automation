# Character reference assets

The normal-video reference engine looks for optional canonical images under:

`assets/character_references/<character-name>/`

Supported formats: JPG, JPEG, PNG, WEBP.

The character name is normalized to lowercase with spaces and punctuation replaced by underscores. For example, `Milo The Brave` becomes `assets/character_references/milo_the_brave/`.

No reference image is required for the pipeline to run. Without one, the manifest marks the scene as `prompt_only`. When a reference exists, its SHA-256 fingerprint is recorded so accidental asset replacement can be detected.

Recommended reference set:
- front view
- three-quarter view
- full-body view
- neutral expression
- clean/uncluttered background

Do not commit private or copyrighted images unless you have permission to use them.
