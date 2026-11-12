# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.
# Adapted from Redmine AI Helper (MIT), Copyright (c) 2025 Haruyuki Iida.
# See LICENSES/redmine_ai_helper-MIT.txt for the original notice.

require "redmine_ai_helper/base_agent"
require_relative "dmsf_tools"

module RedmineAiHelperDmsf
  # Independently registered, read-only agent for the DMSF extension.
  #
  # AI Helper registers agents by their short class name. The distinct
  # DmsfExtensionAgent basename avoids replacing the source fork's DmsfAgent.
  class DmsfExtensionAgent < RedmineAiHelper::BaseAgent
    # @return [Boolean] whether DMSF access and attachment sharing are enabled
    def enabled?
      DmsfTools.enabled?
    end

    # Loads this plugin's localized instructions, with an English fallback.
    # AI Helper's own prompt loader only reads its upstream assets directory.
    # @return [String] instructions for document discovery and analysis
    def backstory
      key = "redmine_ai_helper_dmsf.agent_backstory"
      I18n.t(key, default: I18n.t(key, locale: :en))
    end

    # Preserve BaseAgent's filtering by exposing providers through its API.
    # @return [Array<Class>] the extension's read-only tool provider
    def available_tool_providers
      [DmsfTools]
    end
  end
end

