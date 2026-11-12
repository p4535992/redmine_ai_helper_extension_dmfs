# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.
# Plugin structure adapted from Redmine AI Helper (MIT),
# Copyright (c) 2025 Haruyuki Iida. See LICENSES/redmine_ai_helper-MIT.txt.

require_relative "version"

Redmine::Plugin.register :redmine_ai_helper_extension_dmfs do
  name "Redmine AI Helper DMSF Extension"
  author "p4535992"
  description "Read-only DMSF document discovery and analysis for Redmine AI Helper."
  version RedmineAiHelperDmsf::VERSION
  url "https://github.com/p4535992/redmine_ai_helper_extension_dmfs"
  author_url "https://github.com/p4535992"
  requires_redmine version_or_higher: "6.1.0"
  requires_redmine_plugin :redmine_ai_helper, version_or_higher: "3.13.0"
end

# The required folder name loads after redmine_ai_helper. Check its version
# before loading subclasses. DMSF loads later; its availability is checked by
# DmsfTools at request time, without loading or modifying DMSF during startup.
require_relative "lib/redmine_ai_helper_dmsf/dmsf_extension_agent"

