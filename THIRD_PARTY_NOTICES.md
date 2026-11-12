# Third-party notices and provenance

## License of this extension

Redmine AI Helper DMSF Extension is distributed under the **GNU General Public
License, version 3 or (at your option) any later version**
(`SPDX-License-Identifier: GPL-3.0-or-later`). The complete GPL version 3 text is
in [LICENSE](LICENSE).

Copyright (C) 2026 p4535992 and contributors, for the extension-specific changes.
Existing upstream copyrights and notices remain applicable.

The extension is a separate Redmine plugin that runs in the same Ruby process as
AI Helper and DMSF. GPL-3.0-or-later is chosen to be compatible with the
MIT-licensed code adapted from AI Helper and the GPL-3.0-or-later DMSF dependency.
This choice does not change the licenses of those upstream projects.

## Adapted AI Helper code (MIT)

The DMSF agent, tools, prompts, tests and integration documentation were extracted
and adapted from:

- Repository: <https://github.com/p4535992/redmine_ai_helper>
- Branch: `feature/dmsf-readonly-tools-20261111`
- Source commit: `89d4d014819ea6b29c572d4d11551bc7a1793185`
- Upstream project: <https://github.com/haru/redmine_ai_helper>
- Upstream copyright: **Copyright (c) 2025 Haruyuki Iida**
- Original license: **MIT**
- Original license blob: `ecfcd4670a3ddfffd30ae8ffb224762e91b36be9`

The separate-plugin structure follows AI Helper's
[`example/redmine_fortune/`](https://github.com/haru/redmine_ai_helper/tree/10362446a2eefd814ae76c6ec23094bddfc3cfe6/example/redmine_fortune)
example. The source branch and the upstream project have the same MIT license
text. That original copyright and the complete permission/warranty notice are
preserved verbatim in
[LICENSES/redmine_ai_helper-MIT.txt](LICENSES/redmine_ai_helper-MIT.txt).

The original portions retain their MIT permissions. Distributing this combined
extension under GPL-3.0-or-later does not remove those original permissions or
the obligation to preserve the MIT notice. Extension-specific modifications are
provided under GPL-3.0-or-later.

## Runtime dependency: Redmine DMSF

- Project: <https://github.com/picman/redmine_dmsf>
- Authors credited by DMSF: **Vít Jonáš / Daniel Munn / Karel Pičman**
- License: **GPL-3.0-or-later**
- Reviewed commit: `fceb0b694a59ff98f044b39c45d7b218bb836268`
- [License text](https://github.com/picman/redmine_dmsf/blob/fceb0b694a59ff98f044b39c45d7b218bb836268/LICENSE.md)
- [Explicit version-3-or-later grant in init.rb](https://github.com/picman/redmine_dmsf/blob/fceb0b694a59ff98f044b39c45d7b218bb836268/init.rb)

DMSF must be installed separately. Its implementation is not bundled in this
repository. The extension calls DMSF's APIs; this repository does not purport to
relicense DMSF.

## Runtime dependency: Redmine

- Project: <https://github.com/redmine/redmine>
- Copyright notice: **Copyright (C) 2006- Jean-Philippe Lang**
- License: **GPL-2.0-or-later**
- Reviewed commit: `bc6b64ea63ab9b3efacbcdf6b8fb494c9560b875`
- [License text](https://github.com/redmine/redmine/blob/bc6b64ea63ab9b3efacbcdf6b8fb494c9560b875/doc/COPYING)
- [Explicit version-2-or-later grant](https://github.com/redmine/redmine/blob/bc6b64ea63ab9b3efacbcdf6b8fb494c9560b875/app/models/project.rb)

Redmine must be installed separately and is not bundled. Its "or any later
version" grant permits use under GPL version 3 when combined with GPLv3 code;
this is different from GPL-2.0-only.

## Compatibility and redistribution

The MIT license permits modification and redistribution with its original
copyright and permission notice retained. The Free Software Foundation describes
the compatibility of permissive licenses and the effect of combining works under
compatible licenses in
[License Compatibility and Relicensing](https://www.gnu.org/licenses/license-compatibility.en.html).
Its [license identification guidance](https://www.gnu.org/licenses/identify-licenses-clearly.html)
also explains compatibility between GPL-2.0-or-later and GPL-3.0-or-later.

When distributing this extension or a modified version, retain LICENSE and the
third-party notices, mark modifications appropriately, and provide the
corresponding source under the applicable GPL terms. If distributing a bundle
that includes Redmine, DMSF, AI Helper or their dependencies, preserve each
component's notices and satisfy that component's redistribution requirements.
